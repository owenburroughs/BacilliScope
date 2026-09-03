# This is a test program so I can work out some of the specifics with my zmq-based cellpose server
import zmq 
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--message', '-m', help="Message to send to the cellpose server.", type=str, default='test')
    args = vars(parser.parse_args())
    
    
    message_json = {
        'message_type' : 'cellpose_job',
        'input_file' : 't1_A01_s1_w1_z1.tif',
        'output_file' : 'output.tif',
        'diameter' : 30,
        'resample' : False,
        'batch_size' : 8,
        'min_size' : 100
    }
    
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    socket.connect("ipc:///tmp/bacilliscope")
    socket.send_json(message_json)
    message = socket.recv()
    print(f"Received: {message}")