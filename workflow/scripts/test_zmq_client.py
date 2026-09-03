# This is a test program so I can work out some of the specifics with my zmq-based cellpose server
import zmq 
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--message', '-m', help="Message to send to the cellpose server.", type=str, default='test')
    args = vars(parser.parse_args())
    
    
    
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    socket.connect("ipc://bacilliscope")
    socket.send(args['message'].encode())
    message = socket.recv()
    print(f"Received: {message}")