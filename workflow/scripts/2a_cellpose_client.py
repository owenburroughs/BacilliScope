#-----------------------------------------------------------------------------------
# CELLPOSE CLIENT
#
# The purpose of this script is to recieve a cellpose job from the snakefile and send it
# to the cellpose server.
# We must also check if the server is running, and if it is not, we need to start the server,
# using a unique lock token to make sure we are the only ones doing this.
# Finally, we will send the cellpose job to the server and get a response.
#-----------------------------------------------------------------------------------

import zmq 
import argparse
import random
import psutil

import sys
import subprocess
import os
import time

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from snakemake.iocontainers import snakemake

SERVER_PROCESS_NAME = 'cellpose-server-406mt'
NEW_SERVER_TIMEOUT_MS = 5000
NEW_SERVER_TRIES = 20

CELLPOSE_TIMEOUT = 10000
CELLPOSE_TRIES = 1

verbose = True

# DEBUG (VERBOSE) PRINTING
def debug(message:str)->None:
    if verbose:
        print(message)

# ----------------------------------------------------------------------------------
# MAIN FUNCTION TO SEND A CELLPOSE JOB
# ----------------------------------------------------------------------------------
def send_cellpose_job(
    input_file: str,
    output_file: str,
    diameter: float,
    resample: bool,
    batch_size: int,
    min_size: int,
    socket_path: str,
    snakemake_PID: str
)-> int:
    #to-do lock communication with the server so we only have one request at a time?
    
    cellpose_job_message = {
            'message_type' : 'cellpose_job',
            'input_file' : input_file,
            'output_file' : output_file,
            'diameter' : diameter,
            'resample' : resample,
            'batch_size' : batch_size,
            'min_size' : min_size
        }
    
    
    debug('Sending cellpose job to server')
    #----------- Try to send our cellpose job -------------
    cellpose_result = message_to_server(
        message = cellpose_job_message,
        socket_path=socket_path,
        timeout=CELLPOSE_TIMEOUT,
        max_tries=CELLPOSE_TRIES
    )
    
    # Did we get a response back from the server?
    if cellpose_result != None:
        return cellpose_result['response_status']
    
    # The server didn't send a result, (re)start it
    debug("Initial cellpose job didn't recieve a response")
    
    server_status = start_cellpose_server(
                        socket_path=socket_path,
                        snakemake_pid=snakemake_PID
                    )
    
    if server_status != 0:
        raise Exception("Error starting cellpose server")
    else:
        debug("Cellpose server started successfully")
    
    # Try the Cellpose job again
    cellpose_result = message_to_server(
            message = cellpose_job_message,
            socket_path=socket_path,
            timeout=CELLPOSE_TIMEOUT,
            max_tries=CELLPOSE_TRIES
        )
        
    # Did we get a response back from the server?
    if cellpose_result != None:
        return cellpose_result['response_status']
    else:
        raise Exception("Cellpose job failed even after restarting server.")


# ----------------------------------------------------------------------------------
# SEND MESSAGE TO SERVER
# ----------------------------------------------------------------------------------
def message_to_server(
    message: object,
    socket_path: str,
    timeout: int,
    max_tries: int
) -> object | None:
    
    #Create our connection to server
    context = zmq.Context()
    
    # First, generate a unique ID for this request
    request_id = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=8))
    
    # Set the request ID for the message
    message['request_id'] = request_id
    
    #--------- Try to send the message ----------------------
    tries = 0
    
    while tries < max_tries:
        socket = context.socket(zmq.REQ)
        socket.setsockopt(zmq.LINGER, 0)
        socket.connect(f"ipc://{socket_path}")
        socket.setsockopt(zmq.RCVTIMEO, timeout)
        
        
        socket.send_json(message)
        
        try:
            recieved_message = socket.recv_json()
            
            if recieved_message['response_id'] == request_id:
                socket.close()
                context.term()
                return recieved_message
            else:
                raise Exception('Invalid response recieved by cellpose client')
            
        # Exception for exceeded timeout
        except zmq.error.Again:
            socket.close()
            tries += 1
            continue
        
        # Catch-all exception
        except Exception as e:
            raise Exception(f'ERROR: {e}')
    
    #--------- Message wasn't successful after max tries, return None -----------------
    socket.close()
    context.term()
    return None
    


# ----------------------------------------------------------------------------------
# (RE)START CELLPOSE SERVER
# 
#   Returns 0 on success
# ----------------------------------------------------------------------------------
def start_cellpose_server(
        socket_path: str,
        snakemake_pid: int
    )-> int:
    debug("(Re)starting cellpose server.")
    #------------- Are there any cellpose servers running? -------------------------
    for process in psutil.process_iter(['name']):
        if process.info['name'] == SERVER_PROCESS_NAME:
            print("Found an existing cellpose server. Killing.")
            process.kill()

    #------------- Start a new cellpose server process -------------------------
    debug("Starting a new cellpose server.")
    server = subprocess.Popen(
        [
            sys.executable,
            "3b_cellpose_server.py",
            "--owner-pid", str(snakemake_pid),
            "--socket-path", socket_path,
            "--process-name", SERVER_PROCESS_NAME
        ],
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    
    #------------- Try to ping the server so we know its alive -------------------------        
    ping_response = message_to_server(
        message= {'message_type' : 'ping'},
        socket_path = socket_path,
        timeout = NEW_SERVER_TIMEOUT_MS,
        max_tries= NEW_SERVER_TRIES
    )
    
    if ping_response == None:
        raise Exception("Error starting new cellpose server.")
    
    elif ping_response['response_text'] != 'pong':
        raise Exception("Error starting new cellpose server.")
    else:
        # Server startup was successful and it is ready to recieve messages
        return 0

# ----------------------------------------------------------------------------------
# MAIN FUNCTION
# ----------------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        input_file = snakemake.input
        output_file = snakemake.output
        diameter = snakemake.params['diameter']
        resample = snakemake.params['resample']
        batch_size = snakemake.params['batch_size']
        min_size = snakemake.params['min_size']
        snakemake_PID = snakemake.params['snakemake_PID']
        socket_path = snakemake.params['socket_path']
                
    except NameError:
        parser = argparse.ArgumentParser()
        # Cellpose parameters
        parser.add_argument('--input-file', '-i', help="Input file for cellpose.", type=str)
        parser.add_argument('--output-file', '-o', help="Output file for cellpose.", type=str)
        parser.add_argument('--diameter', '-d', help="Diameter param for cellpose.", type=float)
        parser.add_argument('--resample', '-r', help="Resample parameter for cellpose.", action='store_true')
        parser.add_argument('--batch-size', '-b', help="Batch size parameter for cellpose.", type=int)
        parser.add_argument('--min-size', '-m', help="Min size parameter for cellpose.", type=int)

        # Server startup parameters
        parser.add_argument('--snakemake-PID', '-p', help="The PID of the snakemake process. Passed to the server to dictate shutdown behavior.", type=int, default=-1)
        parser.add_argument('--socket-path', '-k', help="Path to the socket used for IPC communication with the server.", type=str, default='/tmp/cellpose_server.sock')

        args = vars(parser.parse_args())
        input_file= args['input_file']
        output_file= args['output_file']
        diameter= args['diameter']
        resample= args['resample']
        batch_size= args['batch_size']
        min_size= args['min_size']
        socket_path= args['socket_path']
        snakemake_PID= args['snakemake_PID']
    except Exception as e:
        print(e)
        sys.exit(1)
    
    # For debugging: set snakemake PID to current PID if not passed (this will usually be the terminal)
    if snakemake_PID == -1:
        snakemake_PID = os.getpid()
    
    start_time = time.time()
    
    return_val = send_cellpose_job(
                    input_file= args['input_file'],
                    output_file= args['output_file'],
                    diameter= args['diameter'],
                    resample= args['resample'],
                    batch_size= args['batch_size'],
                    min_size= args['min_size'],
                    socket_path= args['socket_path'],
                    snakemake_PID= snakemake_PID
                )
    
    end_time = time.time()
    
    debug(f'Cellpose job ran in {end_time-start_time} seconds.')
    
    sys.exit(return_val)
    
    
# python3 3a_cellpose_client.py -i 't1_A01_s1_w1_z1.tif' -o 'output.tif' -d 30 -b 8 -m 100 -v