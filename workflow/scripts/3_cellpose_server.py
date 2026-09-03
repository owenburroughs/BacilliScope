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
#-------------------------------------------------------
import argparse
import os
from time import sleep
import zmq
import psutil

DMS_MAX = 30 # Maximum allowed value for the dead man's switch counter
RCV_TIMEOUT = 10000 # Timeout (ms) for the recv() function so we don't infinitely wait

class CellposeServer():
    def __init__(
            self, 
            socket_path:str
        ):
        # Set up the zmq socket as in request-reply as a reciever
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REP) # This is the reply part of the request-reply pattern
        self.socket.bind("ipc://bacilliscope")
        self.socket.RCVTIMEO = RCV_TIMEOUT # Timeout (ms) for the recv() function so we don't infinitely wait
        print('Server binding to IPC')
        
        #Get parent process id and store a process
        self.parent_process = psutil.Process(os.getppid())
        self.DMS_counter = 0 # Dead man's switch counter to make sure the server is never open for infinitely long
        
    
    def start_listener(self):
        #Listen for zmq messages and reply with a response
        while True:
            try:
                # Blocking operation to get the message
                message = self.socket.recv()
                
                # What we do next depends on what the message was
                match message:
                    case b"ping":
                        self.socket.send(b"pong")
                        
                    case b"exit":
                        self.socket.send(b"Shutting down Cellpose server")
                        self.shutdown()
                        break
                    
                    case _:
                        print(f"Server received request: {message}")
                        sleep(1)
                        self.socket.send(b"Message Received")
                        
                self.DMS_counter = 0 # Reset the DMS Counter
                        
            except zmq.error.Again:
                # The timeout period was exceeded without recieving a message, check if the parent process is still alive
                if self.parent_is_alive():
                    # Exit if the DMS is tripped
                    if (self.DMS > self.DMS_max):
                        print("Parent process still reports to be alive, but the dead man's switch was tripped due to inactivity. Exiting the server.")
                        self.shutdown()
                        break
                    
                    # Parent process is alive. Don't exit but increment the DMS counter
                    print("Message timeout exceeded but parent process is still running.", flush=True)
                    self.DMS = self.DMS + 1
                else:
                    print("Message timeout exceeded and parent process is dead. Exiting.", flush=True)
                    self.shutdown()
                    break
        
    # Return whether the parent is alive
    def parent_is_alive(self):
        try:
            return (
                self.parent_process.is_running()
                and self.parent_process.status() != psutil.STATUS_ZOMBIE
            )
        except psutil.NoSuchProcess:
            return False
    
    # Shutdown the Cellpose server
    def shutdown(self):
        self.socket.setsockopt(zmq.LINGER, 0)
        self.socket.close()
        self.context.term()


if __name__ == "__main__":
    #Load arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--socket_path', '-s', help="Path for the IPC socket used to communicate with this process.", type=str, default='/tmp/bacilliscope')  
    args = vars(parser.parse_args())
    server = CellposeServer(
                socket_path=args['socket_path']
            )
    server.start_listener()