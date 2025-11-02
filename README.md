# HW3_-modern_computer_networks

## Архитектура

- **p2p_client.py** - единый клиент для всех сценариев
- **rendezvous_server.py** - сервер для установления P2P соединений
- **traf/3.pcapng** - захваченный трафик (оба клиента за NAT)
- **traf/3_clean** - отфильтрованный трафик

## Запуск

### Сервер:
```bash
    python3 rendezvous_server.py
```

### Клиент
```bash
    python3 p2p_client.py <client<id>> <server<ip>>
```

### Пример работы
```text
    > connect client2
    > send abiba aboba abubu
```


### Что происходит?
```text
192.168.100.2 (PC2)    192.168.100.10 (Сервер)    192.168.100.3 (PC3)
─────────────────────────────────────────────────────────────────────
                       
Фаза 1: Регистрация на сервере
                       
UDP 44826 → 8888 (Len=80)
UDP 8888 → 44826 (Len=67)
Сервер сообщает клиентам друг о друге
UDP 8888 → 44826 (Len=131)
                       
Фаза 2: Пробивание NAT (Hole Punching)
                       
["type": "punch", "from": "pc3"]
["type": "punch", "from": "pc2"]
["type": "punch_ack", "from": "pc2"]
["type": "punch_ack", "from": "pc3"]
                       
Фаза 3: Обмен сообщениями
                       
["type": "message", "text": "hello"]
                       
Фаза 4: Дальнейший обмен
                       
["type": "message", "text": "hello"]
["type": "message", "text": "aboba abiba..."]
["type": "message", "text": "hhhhhhhhhhhh"]
```