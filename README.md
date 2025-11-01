# HW3_-modern_computer_networks

## Архитектура

- **p2p_client.py** - единый клиент для всех сценариев
- **rendezvous_server.py** - сервер для установления P2P соединений
- **HW3.pcapng** - захваченный трафик (оба клиента за NAT)
- **HW3_clean.pcapng** - отфильтрованный трафик

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
