#!/usr/bin/env python3
import socket
import json
import threading
import logging
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class RendezvousServer:
    def __init__(self, host='0.0.0.0', port=8888):
        self.host = host
        self.port = port
        self.clients = {}
        
    def start(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((self.host, self.port))
        logging.info(f"Сервер запущен на {self.host}:{self.port}")
        
        while True:
            data, addr = sock.recvfrom(1024)
            threading.Thread(target=self.handle_client, args=(data, addr, sock), daemon=True).start()
    
    def handle_client(self, data, client_addr, sock):
        try:
            message = json.loads(data.decode())
            client_id = message.get('client_id')
            msg_type = message.get('type')
            
            logging.info(f"Получено {msg_type} от {client_id} с адреса {client_addr}")
            
            if msg_type == 'register':
                self.clients[client_id] = {
                    'private_addr': message.get('local_addr', client_addr),
                    'public_addr': client_addr
                }
                
                response = {
                    'type': 'registered', 
                    'your_public_addr': list(client_addr)
                }
                sock.sendto(json.dumps(response).encode(), client_addr)
                logging.info(f"Клиент {client_id} зарегистрирован")
                
            elif msg_type == 'connect_request':
                target_id = message.get('target_id')
                
                if target_id not in self.clients:
                    response = {'type': 'peer_not_found'}
                    sock.sendto(json.dumps(response).encode(), client_addr)
                    return
                
                client_a = self.clients[client_id]
                client_b = self.clients[target_id]
                
                response_a = {
                    'type': 'peer_info', 
                    'peer_id': target_id,
                    'peer_private_addr': list(client_b['private_addr']),
                    'peer_public_addr': list(client_b['public_addr'])
                }
                sock.sendto(json.dumps(response_a).encode(), client_a['public_addr'])
                
                response_b = {
                    'type': 'peer_info',
                    'peer_id': client_id,
                    'peer_private_addr': list(client_a['private_addr']),
                    'peer_public_addr': list(client_a['public_addr'])
                }
                sock.sendto(json.dumps(response_b).encode(), client_b['public_addr'])
                
                logging.info(f"Обмен информацией между {client_id} и {target_id}")
                
        except Exception as e:
            logging.error(f"Ошибка: {e}")

if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else '0.0.0.0'
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8888
    
    server = RendezvousServer(host, port)
    server.start()