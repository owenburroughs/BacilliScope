#------------------------------------------------------
# CELLPOSE SERVER:
# This script is launched by the snakemake pipeline, and is responsible
# for initializing cellpose and then running it on individual files passed
# to it. I need to do the following:
#
# 1. Open a Zero MQ IPC socket so server and client can communicate
# 2. Initialize Cellpose
# 3. Poll the socket for new requests
# 4. When a job is recieved, run cellpose on it and return the output
# 5. At regular intervals, check if the parent process is running, and kill this process if it isn't
#
# COMMUNICATION PROTOCOL - 
#   (1) Client sends message in the form of the following object (serialized as JSON):
#       {
#           message_type: string = ("cellpose_job" | "ping" | "exit")
#           request_id: str // 8-character string we use to confirm that the response for a job matches the request
#           input_file: string // the global path to the input filename for a cellpose job
#           output_file: string // the global path to the output filename for a cellpose job
#           diameter: float // diameter to pass to cellpose model
#           resample: boolean // cellpose resample parameter
#           batch_size: int // cellpose batch size parameter
#           min_size: int // cellpose minimum size paramter
#       }
#
#   (2) Server responds with the following object (serialized as JSON):
#       {
#           response_id: str // 8-character string that was the message ID for the request
#           response_status: int // 0 if successful, all else is a failure
#           response_string: str // optional string to append to response
#       }
#-------------------------------------------------------

import argparse
import os
import zmq
import psutil
import json
import time
import setproctitle as spt

from cellpose import models
from PIL import Image
import numpy as np


DMS_MAX = 30 # Maximum allowed value for the dead man's switch counter
RCV_TIMEOUT = 10000 # Timeout (ms) for the recv() function so we don't infinitely wait
RUNTIME_REPORT_INTERVAL = 1 #How often do we report the average runtimes of cellpose

class CellposeServer():
    def __init__(
            self, 
            socket_path:str,
            process_name:str,
            owner_pid:int
        ):
        
        # Set up the zmq socket as in request-reply as a reciever
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REP) # This is the reply part of the request-reply pattern
        self.socket.bind(f"ipc://{socket_path}")
        self.socket.RCVTIMEO = RCV_TIMEOUT # Timeout (ms) for the recv() function so we don't infinitely wait
        print(f'Cellpose server binding to IPC at socket ipc://{socket_path}.', flush=True)
        
        # Get parent process id and store a process
        self.parent_process = psutil.Process(owner_pid)
        self.DMS_counter = 0 # Dead man's switch counter to make sure the server is never open for infinitely long
        
        # Set up the cellpose instance
        print("Initializing cellpose model.", flush=True)
        self.model = models.Cellpose(model_type='cyto3', gpu=True)
        
        # Create a list to store cellpose runtimes
        self.runtimes = []
        
        # Set the process title for this server
        spt.setproctitle(process_name)
        
        print("Cellpose server initialized.")
        
    #-------------------------------------------------
    # MAIN ZMQ LISTENER LOOP
    #-------------------------------------------------
    def start_listener(self):
        print("Listening for cellpose messages")
        #------------------  Listen for ZMQ messages and reply with a response --------------
        while True:
            try:
                # Blocking operation to get the message, which should be in JSON format
                message = self.socket.recv_json()
                
                #-------------- Validate the JSON object ------------------------------------
                if not "message_type" in message.keys():
                    print("ERROR: message_type was not provided in the request.")
                    self.socket.send(b"ERROR: message_type was not provided in the request.")
                    continue
                
                if not "request_id" in message.keys():
                    print("ERROR: requests must contain a request_id.")
                    self.socket.send(b"ERROR: requests must contain a request_id.")
                    continue
                
                if not message["message_type"] in ['cellpose_job', 'ping', 'exit']:
                    return_message = f"ERROR: Unknown message type {message['message_type']}."
                    print(return_message)
                    self.socket.send(return_message.encode())
                    continue
                
                #--------------- What we do next depends on what the message was -------------
                response_id = message['request_id']
                
                match message['message_type']:
                    case "ping":
                        self.socket.send_json({
                            'response_id' : response_id,
                            'response_status' : 0,
                            'response_text' : 'pong'
                        })
                        
                    case "exit":
                        self.socket.send_json({
                            'response_id' : response_id,
                            'response_status' : 0,
                            'response_text' : 'Shutting down cellpose server.'
                        })
                        self.shutdown()
                        break
                    
                    case 'cellpose_job':
                        # --- make sure we have the right parameters for a cellpose job -------
                        for required_key in ['input_file', 'output_file', 'diameter', 'resample', 'batch_size', 'min_size']:
                            # to-do, validate types here with pydantic?
                            if not required_key in message.keys():
                                return_message = f'ERROR: Key {required_key} is required for message type "cellpose_job"'
                                print(return_message)
                                self.socket.send_json({
                                    'response_id' : response_id,
                                    'response_status' : 1,
                                    'response_text' : return_message
                                })
                                
                        # Finally, send the validated job to be run through cellpose
                        try: 
                            self.run_cellpose(
                                input_file = message['input_file'],
                                output_file = message['output_file'],
                                diameter = message['diameter'],
                                resample = message['resample'],
                                batch_size = message['batch_size'],
                                min_size = message['min_size']
                            )
                            
                            self.socket.send_json({
                                'response_id' : response_id,
                                'response_status' : 0,
                                'response_text' : 'Cellpose completed successfully.'
                            })
                            
                        except Exception as e:
                            return_message = f'ERROR: {e}'
                            print(return_message)
                            self.socket.send_json({
                                'response_id' : response_id,
                                'response_status' : 1,
                                'response_text' : return_message
                            })
                            continue
                        
                self.DMS_counter = 0 # Reset the DMS Counter
                        
            #--------------------- Exception for non-JSON message recieved --------------------
            except json.decoder.JSONDecodeError:
                print("ERROR: Message was not encoded in JSON format.")
                self.socket.send(b"ERROR: Message was not encoded in JSON format.")
                continue                
                        
            #----------------------- Exception for exceeded timeout ---------------------------            
            except zmq.error.Again:
                # The timeout period was exceeded without recieving a message, check if the parent process is still alive
                if self.parent_is_alive():
                    # Exit if the DMS is tripped
                    if (self.DMS_counter > DMS_MAX):
                        print("Parent process still reports to be alive, but the dead man's switch was tripped due to inactivity. Exiting the server.")
                        self.shutdown()
                        break
                    
                    # Parent process is alive. Don't exit but increment the DMS counter
                    self.DMS_counter = self.DMS_counter + 1
                else:
                    print("Message timeout exceeded and parent process is dead. Exiting.", flush=True)
                    self.shutdown()
                    break
                
    #-------------------------------------------------
    # RUN CELLPOSE
    #-------------------------------------------------
    def run_cellpose(
            self,
            input_file: str,
            output_file: str,
            diameter: float,
            resample: bool,
            batch_size: int,
            min_size: int
    ):
        start_time = time.time()
        input_image = Image.open(input_file)
        image_array = np.asarray(input_image)
        
        mask, flows, styles, diams = self.model.eval(
                    image_array, 
                    channels=[0,0], 
                    diameter=diameter, 
                    resample=resample, 
                    batch_size=batch_size,
                    min_size = min_size
                )
        
        mask_image = Image.fromarray(mask)
        mask_image.save(output_file, compression='tiff_adobe_deflate')
        
        # Add the runtime to our list
        self.runtimes.append(time.time() - start_time)
        
        # Report the average runtime if we hit our interval
        if (len(self.runtimes) % RUNTIME_REPORT_INTERVAL) == 0:
            print(f'Cellpose ran in {self.runtimes[-1]}')
            print(f'Run cellpose {len(self.runtimes)} times with an average of {np.mean(self.runtimes)} seconds per image.')
        
    #-------------------------------------------------
    # RETURN WHETHER PARENT PROCESS IS ALIVE
    #-------------------------------------------------
    def parent_is_alive(self):
        try:
            return (
                self.parent_process.is_running()
                and self.parent_process.status() != psutil.STATUS_ZOMBIE
            )
        except psutil.NoSuchProcess:
            return False
    
    #-------------------------------------------------
    # SHUTDOWN THE SERVER
    #-------------------------------------------------
    def shutdown(self):
        self.socket.setsockopt(zmq.LINGER, 0)
        self.socket.close()
        self.context.term()


if __name__ == "__main__":
    #Load arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--socket-path', '-s', help="Path for the IPC socket used to communicate with this process.", type=str, default='/tmp/cellpose_server.sock') 
    parser.add_argument('--owner-pid', '-o', help="PID for the process that owns this process.", type=int, default=-1)  
    parser.add_argument('--process-name', '-p', help="Name for this process.", type=str, default='cellpose-server-406mt')  
    args = vars(parser.parse_args())
    
    # For debugging: set PID to parent PID if not passed (this will usually be the terminal)
    owner_pid = args['owner_pid']
    if owner_pid == -1:
        owner_pid = os.getppid()
    
    server = CellposeServer(
                socket_path=args['socket_path'],
                process_name=args['process_name'],
                owner_pid= owner_pid
            )
    server.start_listener()