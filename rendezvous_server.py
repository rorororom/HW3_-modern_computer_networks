#!/usr/bin/env python3
import socket
import threading
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class RendezvousServer:
    def __init__(self, host='0.0.0.0', port=8888):
        self.host = host
        self.port = port
        self.clients = {}
        
    def start(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((self.host, self.port))
        logging.info(f"Rendezvous server started on {self.host}:{self.port}")
        
        while True:
            data, addr = sock.recvfrom(1024)
            threading.Thread(target=self.handle_client, args=(data, addr, sock)).start()
    
    def handle_client(self, data, addr, sock):
        try:
            message = json.loads(data.decode())
            client_id = message.get('client_id')
            msg_type = message.get('type')
            
            if msg_type == 'register':
                public_addr = message.get('public_addr', addr)
                self.clients[client_id] = {
                    'private_addr': addr,
                    'public_addr': public_addr
                }
                logging.info(f"Client {client_id} registered: private={addr}, public={public_addr}")
                
                response = {'type': 'registered', 'your_public_addr': public_addr}
                sock.sendto(json.dumps(response).encode(), addr)
                
            elif msg_type == 'connect_request':
                target_id = message.get('target_id')
                if target_id in self.clients:
                    client_a_info = self.clients[client_id]
                    client_b_info = self.clients[target_id]
                    
                    response_a = {
                        'type': 'peer_info', 
                        'peer_id': target_id,
                        'peer_private_addr': client_b_info['private_addr'],
                        'peer_public_addr': client_b_info['public_addr']
                    }
                    sock.sendto(json.dumps(response_a).encode(), client_a_info['private_addr'])
                    
                    response_b = {
                        'type': 'peer_info',
                        'peer_id': client_id, 
                        'peer_private_addr': client_a_info['private_addr'],
                        'peer_public_addr': client_a_info['public_addr']
                    }
                    sock.sendto(json.dumps(response_b).encode(), client_b_info['private_addr'])
                    
                    logging.info(f"Connected {client_id} with {target_id}")
                else:
                    response = {'type': 'peer_not_found'}
                    sock.sendto(json.dumps(response).encode(), addr)
                    
        except Exception as e:
            logging.error(f"Error: {e}")

if __name__ == "__main__":
    server = RendezvousServer()
    server.start()