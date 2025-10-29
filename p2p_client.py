#!/usr/bin/env python3
import socket
import json
import threading
import time
import logging
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class P2PClient:
    def __init__(self, client_id, server_host, server_port=8888):
        self.client_id = client_id
        self.server_addr = (server_host, server_port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(3.0)
        self.peer_private_addr = None
        self.peer_public_addr = None
        self.connected_peer_addr = None
        self.connected = False
        self.punching = False
        
    def get_public_address(self):
        """Определяет публичный адрес через подключение к серверу"""
        try:
            temp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            temp_sock.connect(self.server_addr)
            public_ip, public_port = temp_sock.getsockname()
            temp_sock.close()
            return [public_ip, public_port]
        except:
            return list(self.sock.getsockname())
    
    def register(self):
        public_addr = self.get_public_address()
        message = {
            'type': 'register', 
            'client_id': self.client_id,
            'public_addr': public_addr
        }
        self.sock.sendto(json.dumps(message).encode(), self.server_addr)
        
        try:
            data, addr = self.sock.recvfrom(1024)
            response = json.loads(data.decode())
            if response['type'] == 'registered':
                logging.info(f"Registered with server. Public addr: {response['your_public_addr']}")
                return True
        except Exception as e:
            logging.error(f"Registration failed: {e}")
        return False
    
    def connect_to_peer(self, peer_id):
        message = {'type': 'connect_request', 'client_id': self.client_id, 'target_id': peer_id}
        self.sock.sendto(json.dumps(message).encode(), self.server_addr)
        logging.info(f"Requested connection to {peer_id}")
    
    def listen(self):
        while True:
            try:
                data, addr = self.sock.recvfrom(1024)
                message = json.loads(data.decode())
                
                if message['type'] == 'peer_info':
                    self.peer_private_addr = tuple(message['peer_private_addr'])
                    self.peer_public_addr = tuple(message['peer_public_addr'])
                    logging.info(f"Got peer addresses: private={self.peer_private_addr}, public={self.peer_public_addr}")
                    
                    # Ждем чтобы оба клиента начали punching одновременно
                    time.sleep(2)
                    self.start_punching()
                    
                elif message['type'] == 'punch':
                    logging.info(f"Received PUNCH from {addr}")
                    if not self.connected:
                        self.connected = True
                        self.connected_peer_addr = addr
                        self.punching = False
                        logging.info(f"P2P connection established with {addr}!")
                        ack_msg = {'type': 'punch_ack', 'from': self.client_id}
                        self.sock.sendto(json.dumps(ack_msg).encode(), addr)
                        
                elif message['type'] == 'punch_ack':
                    logging.info(f"Received PUNCH_ACK from {addr}")
                    if not self.connected:
                        self.connected = True
                        self.connected_peer_addr = addr
                        self.punching = False
                        logging.info(f"P2P connection confirmed with {addr}!")
                        
                elif message['type'] == 'message':
                    logging.info(f"Message from {message['from']}: {message['text']}")
                    
            except socket.timeout:
                continue
            except Exception as e:
                logging.error(f"Error: {e}")
    
    def start_punching(self):
        self.punching = True
        logging.info("Starting NAT hole punching...")
        
        def punch_worker():
            attempt = 0
            while self.punching and attempt < 20:
                try:
                    punch_msg = {'type': 'punch', 'from': self.client_id}
                    
                    # Отправляем на WAN адрес (private_addr из peer_info - это WAN NAT)
                    if self.peer_private_addr:
                        self.sock.sendto(json.dumps(punch_msg).encode(), self.peer_private_addr)
                        logging.info(f"Attempt {attempt+1}: sent to {self.peer_private_addr}")
                    
                    attempt += 1
                    time.sleep(0.5)
                    
                except Exception as e:
                    logging.error(f"Punch error: {e}")
                    time.sleep(0.5)
            
            if self.punching:
                self.punching = False
                logging.error("Failed to establish P2P connection")
        
        threading.Thread(target=punch_worker, daemon=True).start()
    
    def send_message(self, text):
        if self.connected and self.connected_peer_addr:
            msg = {'type': 'message', 'text': text, 'from': self.client_id}
            self.sock.sendto(json.dumps(msg).encode(), self.connected_peer_addr)
            logging.info(f"Message sent to {self.connected_peer_addr}: {text}")
            return True
        else:
            logging.error(f"Not connected. Status: connected={self.connected}")
            return False
    
    def start(self):
        if not self.register():
            logging.error("Failed to register with server")
            return
        
        threading.Thread(target=self.listen, daemon=True).start()
        
        logging.info("Client started. Commands: connect <id>, send <text>, status, quit")
        
        while True:
            try:
                cmd = input("> ").strip().split(' ', 1)
                if cmd[0] == 'connect' and len(cmd) > 1:
                    self.connect_to_peer(cmd[1])
                elif cmd[0] == 'send' and len(cmd) > 1:
                    self.send_message(cmd[1])
                elif cmd[0] == 'status':
                    status = "connected" if self.connected else "punching" if self.punching else "disconnected"
                    logging.info(f"Status: {status}")
                    logging.info(f"Peer WAN: {self.peer_private_addr}")
                    logging.info(f"Peer LAN: {self.peer_public_addr}")
                    logging.info(f"Connected to: {self.connected_peer_addr}")
                elif cmd[0] == 'quit':
                    break
                else:
                    logging.info("Unknown command")
            except KeyboardInterrupt:
                break
            except Exception as e:
                logging.error(f"Command error: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 p2p_client.py <client_id> <server_ip>")
        sys.exit(1)
    
    client = P2PClient(sys.argv[1], sys.argv[2])
    client.start()