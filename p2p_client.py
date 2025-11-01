#!/usr/bin/env python3
import socket
import json
import threading
import time
import logging
import sys
import ipaddress

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class P2PClient:
    def __init__(self, client_id, server_host, server_port=8888):
        self.client_id = client_id
        self.server_addr = (server_host, server_port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('0.0.0.0', 0))
        self.sock.settimeout(3.0)
        self.peer_private_addr = None
        self.peer_public_addr = None
        self.connected_peer_addr = None
        self.connected = False
        self.punching = False
        self.my_local_ip = self.get_local_ip()
        
    def get_local_ip(self):
        try:
            temp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            temp_sock.connect(self.server_addr)
            local_ip = temp_sock.getsockname()[0]
            temp_sock.close()
            return local_ip
        except:
            return '127.0.0.1'
    
    def are_in_same_network(self, ip1, ip2):
        try:
            network1 = ipaddress.IPv4Network(f"{ip1}/24", strict=False)
            network2 = ipaddress.IPv4Network(f"{ip2}/24", strict=False)
            return network1 == network2
        except:
            return False
    
    def get_public_address(self):
        """Возвращает реальный IP и порт"""
        return [self.my_local_ip, self.sock.getsockname()[1]]
    
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
                    self.analyze_scenario()
                    
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
    
    def analyze_scenario(self):
        peer_public_ip = self.peer_public_addr[0]
        peer_private_ip = self.peer_private_addr[0]
        
        if self.are_in_same_network(self.my_local_ip, peer_public_ip):
            logging.info("SCENARIO 1: Both clients in same LAN - using direct connection")
            self.connected = True
            self.connected_peer_addr = (self.peer_public_addr[0], self.peer_public_addr[1])
            logging.info(f"Direct LAN connection established with {self.connected_peer_addr}!")
        
        elif self.peer_private_addr == self.peer_public_addr:
            logging.info("SCENARIO 2: One client behind NAT - connecting directly")
            self.connected = True
            self.connected_peer_addr = self.peer_public_addr
            logging.info(f"Direct connection established with {self.connected_peer_addr}!")
        
        else:
            logging.info("SCENARIO 3: Both behind different NAT - starting hole punching")
            time.sleep(2)
            self.start_nat_hole_punching()
    
    def start_nat_hole_punching(self):
        self.punching = True
        logging.info("Starting NAT hole punching...")
        
        def punch_worker():
            attempt = 0
            while self.punching and attempt < 15:
                try:
                    punch_msg = {'type': 'punch', 'from': self.client_id}
                    
                    if self.peer_private_addr:
                        self.sock.sendto(json.dumps(punch_msg).encode(), self.peer_private_addr)
                    
                    if self.peer_public_addr:
                        self.sock.sendto(json.dumps(punch_msg).encode(), self.peer_public_addr)
                    
                    logging.info(f"Hole punching attempt {attempt+1}")
                    attempt += 1
                    time.sleep(0.5)
                    
                except Exception as e:
                    logging.error(f"Punch error: {e}")
                    time.sleep(0.5)
            
            if self.punching:
                self.punching = False
                logging.error("NAT hole punching failed")
        
        threading.Thread(target=punch_worker, daemon=True).start()
    
    def send_message(self, text):
        if self.connected and self.connected_peer_addr:
            msg = {'type': 'message', 'text': text, 'from': self.client_id}
            self.sock.sendto(json.dumps(msg).encode(), self.connected_peer_addr)
            logging.info(f"Message sent to {self.connected_peer_addr}: {text}")
            return True
        else:
            logging.error(f"Not connected. Status: connected={self.connected}, peer_addr={self.connected_peer_addr}")
            return False
    
    def start(self):
        if not self.register():
            logging.error("Failed to register with server")
            return
        
        threading.Thread(target=self.listen, daemon=True).start()
        
        logging.info("Universal P2P client started!")
        logging.info(f"My socket: {self.sock.getsockname()}")
        logging.info("Commands: connect <id>, send <text>, status, quit")
        
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
                    logging.info(f"My IP: {self.my_local_ip}")
                    logging.info(f"My socket: {self.sock.getsockname()}")
                    logging.info(f"Peer private (WAN): {self.peer_private_addr}")
                    logging.info(f"Peer public (LAN): {self.peer_public_addr}")
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
        print("Usage: python3 p2p_client_final.py <client_id> <server_ip>")
        sys.exit(1)
    
    client = P2PClient(sys.argv[1], sys.argv[2])
    client.start()