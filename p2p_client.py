#!/usr/bin/env python3
import socket
import json
import threading
import time
import logging
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class P2PClient:
    def __init__(self, client_id, server_host, server_port=8888, local_port=0):
        self.client_id = client_id
        self.server_addr = (server_host, server_port)
        
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('0.0.0.0', local_port))
        self.sock.settimeout(3.0)
        
        self.peer_private_addr = None
        self.peer_public_addr = None
        self.connected_peer_addr = None
        self.connected = False
        self.punching = False
        
        self.local_ip = self._get_local_ip()
        logging.info(f"Сокет привязан к порту: {self.sock.getsockname()[1]}")
        
    def _get_local_ip(self):
        try:
            temp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            temp_sock.connect(self.server_addr)
            local_ip = temp_sock.getsockname()[0]
            temp_sock.close()
            return local_ip
        except:
            return '127.0.0.1'
    
    def register(self):
        message = {
            'type': 'register',
            'client_id': self.client_id,
            'local_addr': [self.local_ip, self.sock.getsockname()[1]]
        }
        
        self.sock.sendto(json.dumps(message).encode(), self.server_addr)
        
        try:
            data, addr = self.sock.recvfrom(1024)
            response = json.loads(data.decode())
            if response['type'] == 'registered':
                logging.info(f"Зарегистрирован на сервере. Публичный адрес: {response['your_public_addr']}")
                return True
        except socket.timeout:
            logging.error("Таймаут регистрации - сервер не отвечает")
        except Exception as e:
            logging.error(f"Ошибка регистрации: {e}")
            
        return False
    
    def connect_to_peer(self, peer_id):
        message = {
            'type': 'connect_request',
            'client_id': self.client_id,
            'target_id': peer_id
        }
        self.sock.sendto(json.dumps(message).encode(), self.server_addr)
        logging.info(f"Запрошено соединение с {peer_id}")
    
    def listen(self):
        while True:
            try:
                data, addr = self.sock.recvfrom(1024)
                message = json.loads(data.decode())
                msg_type = message.get('type')
                
                if msg_type == 'peer_info':
                    self.peer_private_addr = tuple(message['peer_private_addr'])
                    self.peer_public_addr = tuple(message['peer_public_addr'])
                    logging.info(f"Получена информация о пире - приватный: {self.peer_private_addr}, публичный: {self.peer_public_addr}")
                    
                    self.establish_p2p_connection()
                    
                elif msg_type == 'punch':
                    logging.info(f"Получен PUNCH пакет от {addr}")
                    if not self.connected:
                        self.connected = True
                        self.connected_peer_addr = addr
                        self.punching = False
                        logging.info(f"P2P соединение установлено с {addr}")
                        
                        ack_msg = {'type': 'punch_ack', 'from': self.client_id}
                        self.sock.sendto(json.dumps(ack_msg).encode(), addr)
                        logging.info(f"Отправлен PUNCH_ACK к {addr}")
                        
                elif msg_type == 'punch_ack':
                    logging.info(f"Получен PUNCH_ACK от {addr}")
                    if not self.connected:
                        self.connected = True
                        self.connected_peer_addr = addr
                        self.punching = False
                        logging.info(f"P2P соединение подтверждено с {addr}")
                        
                elif msg_type == 'message':
                    logging.info(f"Сообщение от {message['from']}: {message['text']}")
                    
            except socket.timeout:
                continue
            except Exception as e:
                logging.error(f"Ошибка получения сообщения: {e}")
    
    def establish_p2p_connection(self):
        scenario = self._analyze_network_scenario()
        
        if scenario == "same_nat":
            logging.info("Сценарий 1: Оба клиента за одним NAT")
            self.connected = True
            self.connected_peer_addr = self.peer_private_addr
            
        elif scenario == "public_peer":
            logging.info("Сценарий 2: Пир имеет публичный IP")
            self.connected = True
            self.connected_peer_addr = self.peer_public_addr
            
        else:
            logging.info("Сценарий 3: Оба за разными NAT")
            time.sleep(1)
            self.start_nat_hole_punching()
    
    def _analyze_network_scenario(self):
        if self.peer_private_addr == self.peer_public_addr:
            return "public_peer"
        
        our_network = '.'.join(self.local_ip.split('.')[:3])
        peer_private_network = '.'.join(self.peer_private_addr[0].split('.')[:3])
        
        if our_network == peer_private_network:
            return "same_nat"
        
        return "different_nats"
    
    def start_nat_hole_punching(self):
        self.punching = True
        logging.info("Запуск улучшенного NAT hole punching...")
        
        def punching_worker():
            attempts = 0
            max_attempts = 30
            
            while self.punching and attempts < max_attempts and not self.connected:
                try:
                    punch_msg = {'type': 'punch', 'from': self.client_id}
                    
                    if self.peer_private_addr:
                        self.sock.sendto(json.dumps(punch_msg).encode(), self.peer_private_addr)
                    
                    if self.peer_public_addr:
                        self.sock.sendto(json.dumps(punch_msg).encode(), self.peer_public_addr)
                    
                    attempts += 1
                    if attempts % 5 == 0:
                        logging.info(f"Попытка {attempts}/{max_attempts}")
                    
                    time.sleep(0.2)
                        
                except Exception as e:
                    logging.error(f"Ошибка punching: {e}")
                    time.sleep(0.5)
            
            if self.punching and not self.connected:
                self.punching = False
                logging.error("NAT hole punching не удался")
        
        threading.Thread(target=punching_worker, daemon=True).start()
    
    def send_message(self, text):
        if self.connected and self.connected_peer_addr:
            message = {
                'type': 'message',
                'text': text,
                'from': self.client_id
            }
            self.sock.sendto(json.dumps(message).encode(), self.connected_peer_addr)
            logging.info(f"Сообщение отправлено пиру: {text}")
            return True
        else:
            logging.error("Не подключен к пиру")
            return False

    def disconnect(self):
        """Отключение от пира"""
        self.connected = False
        self.punching = False
        self.connected_peer_addr = None
        logging.info("Отключен от пира")
    
    def start(self):
        if not self.register():
            logging.error("Не удалось зарегистрироваться на сервере")
            return
        
        threading.Thread(target=self.listen, daemon=True).start()
        
        logging.info("P2P клиент успешно запущен")
        logging.info("Доступные команды:")
        logging.info("  connect <peer_id> - Подключиться к другому клиенту")
        logging.info("  send <text>       - Отправить сообщение подключенному пиру") 
        logging.info("  status            - Показать статус соединения")
        logging.info("  disconnect        - Отключиться от пира")
        logging.info("  quit              - Выход")
        
        while True:
            try:
                cmd_input = input("> ").strip().split(' ', 1)
                command = cmd_input[0].lower()
                
                if command == 'connect' and len(cmd_input) > 1:
                    self.connect_to_peer(cmd_input[1])
                    
                elif command == 'send' and len(cmd_input) > 1:
                    self.send_message(cmd_input[1])
                    
                elif command == 'status':
                    status = "подключен" if self.connected else "punching" if self.punching else "отключен"
                    logging.info(f"Статус: {status}")
                    if self.connected_peer_addr:
                        logging.info(f"Подключен к: {self.connected_peer_addr}")
                    if self.peer_public_addr:
                        logging.info(f"Публичный адрес пира: {self.peer_public_addr}")
                    if self.peer_private_addr:
                        logging.info(f"Приватный адрес пира: {self.peer_private_addr}")
                        
                elif command == 'disconnect':
                    self.disconnect()
                    
                elif command == 'quit':
                    logging.info("Выход...")
                    break
                    
                else:
                    logging.info("Неизвестная команда")
                    
            except KeyboardInterrupt:
                logging.info("Выход...")
                break
            except Exception as e:
                logging.error(f"Ошибка команды: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Использование: python3 p2p_client_fixed.py <client_id> <server_ip> [local_port]")
        sys.exit(1)
    
    local_port = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    client = P2PClient(sys.argv[1], sys.argv[2], local_port=local_port)
    client.start()