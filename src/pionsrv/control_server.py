import os
import json
import readline
import atexit
from queue import Queue
from swarm_server import DDatagram, UDPBroadcastClient, CMD

history_file = os.path.join(os.path.expanduser("~"), ".my_console_history")
if os.path.exists(history_file):
    readline.read_history_file(history_file)
atexit.register(readline.write_history_file, history_file)


def load_drone_config(config_file: str = "drones_config.json"):
    if os.path.exists(config_file):
        with open(config_file, "r") as f:
            return json.load(f)
    else:
        return {}


#####################################
# Control Server (Консольное приложение)
#####################################

class ControlServer:
    """
    Консольное приложение для отправки команд дронам.
    Синтаксис команд:
      [target] command [параметры]

    Примеры:
      all takeoff                - всем дронам выполнить takeoff
      g:1 takeoff                - дронам группы 1 выполнить takeoff
      g:2 goto 1 1 1 1            - дронам группы 2 выполнить goto с координатами 1 1 1 1
      8001 arm                   - дрону с id 8001 выполнить arm
    """

    def __init__(self, broadcast_port: int = 37020, path_to_config: int = "./scripts/drones_config.json"):
        self.path_to_config = path_to_config
        self.client = UDPBroadcastClient(port=broadcast_port, unique_id=666)
        self.broadcast_port = broadcast_port
        self.receive_queue = Queue()
        # Загружаем конфигурацию групп дронов
        self.drone_config = load_drone_config(path_to_config)
        print("Управляющая консоль запущена.")
        print("Синтаксис команд:")
        print("  - 'all takeoff'                - всем дронам выполнить takeoff")
        print("  - 'g:<group> takeoff'           - дронам группы <group> выполнить takeoff")
        print("  - '8001 arm'                   - дрону с id 8001 выполнить arm")
        print("  - 'updategroup 8001 2'         - для дрона с id 8001 установить группу 2")


    def send_command(self, command: CMD, data: list, target: str = "<broadcast>", group: int = 0) -> None:
        dt = DDatagram()
        dt.command = command.value
        dt.data = data
        if target != "<broadcast>" and not target.startswith("g:"):
            dt.target_id = target
            dt.group_id = self.drone_config.get(target, 0)
        elif target.startswith("g:"):
            try:
                group_id = int(target.split(":")[1])
            except Exception:
                group_id = 0
            dt.group_id = group_id
        serialized = dt.export_serialized()
        self.client.socket.sendto(serialized, ("<broadcast>", self.broadcast_port))
        print(f"Команда {command} с данными {data} отправлена для target='{target}' group={dt.group_id}.")

    def console_loop(self):
        print("Запущен консольный интерфейс управления.")
        while True:
            try:
                line = input("Command> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nВыход из консоли.")
                break
            if not line:
                continue
            parts = line.split()
            if parts[0].lower() in ["exit", "quit"]:
                print("Выход из консоли.")
                break
            if parts[0].lower() == "updategroups":
                self.drone_config = load_drone_config(self.path_to_config)
                for drone_id, group in self.drone_config.items():
                    self.send_command(CMD.SET_GROUP, [group], target=drone_id)
                    print(f"Отправлена команда для дрона {drone_id}: установка группы {group}")
                continue
            target_token = parts[0]
            if target_token.lower() == "all":
                target = "<broadcast>"
            else:
                target = target_token

            if len(parts) < 2:
                print("Не указана команда.")
                continue

            cmd = parts[1].lower()
            if cmd == "set_speed":
                if len(parts) != 6:
                    print("Использование: [target] set_speed vx vy vz yaw_rate")
                    continue
                try:
                    vx, vy, vz, yaw_rate = map(float, parts[2:6])
                    self.send_command(CMD.SET_SPEED, [vx, vy, vz, yaw_rate], target)
                except ValueError:
                    print("Неверные параметры для set_speed")
            if cmd == "setgroup":
                if len(parts) != 3:
                    print("Использование: [target] setgroup <новая_группа>")
                    continue
                try:
                    new_group = int(parts[2])
                    self.send_command(CMD.SET_GROUP, [new_group], target)
                except ValueError:
                    print("Неверное значение для новой группы")
            elif cmd == "goto":
                if len(parts) != 6:
                    print("Использование: [target] goto x y z yaw")
                    continue
                try:
                    x, y, z, yaw = map(float, parts[2:6])
                    self.send_command(CMD.GOTO, [x, y, z, yaw], target)
                except ValueError:
                    print("Неверные параметры для goto")
            elif cmd == "takeoff":
                self.send_command(CMD.TAKEOFF, [], target)
            elif cmd == "land":
                self.send_command(CMD.LAND, [], target)
            elif cmd == "arm":
                self.send_command(CMD.ARM, [], target)
            elif cmd == "disarm":
                self.send_command(CMD.DISARM, [], target)
            elif cmd == "trp":
                self.send_command(CMD.SWARM_ON, [], target)
            elif cmd == "stop":
                self.send_command(CMD.STOP, [], target)
            elif cmd == "save":
                self.send_command(CMD.SAVE, [], target)
            elif cmd == "smart_goto":
                if len(parts) != 6:
                    print("Использование: [target] smart_goto x y z yaw")
                    continue
                try:
                    x, y, z, yaw = map(float, parts[2:6])
                    self.send_command(CMD.SMART_GOTO, [x, y, z, yaw], target)
                except ValueError:
                    print("Неверные параметры для smart_goto")
            elif cmd == "led":
                if len(parts) != 6:
                    print("Использование: [target] led led_id r g b")
                    continue
                try:
                    led_id = int(parts[2])
                    r, g, b = map(int, parts[3:6])
                    self.send_command(CMD.LED, [led_id, r, g, b], target)
                    print(f"Команда LED отправлена: led_id={led_id}, r={r}, g={g}, b={b}")
                except ValueError:
                    print("Неверные параметры для led")
            else:
                print("Неизвестная команда. Доступны: set_speed, goto, takeoff, land, arm, disarm, smart_goto, "
                      "led, updategroups")

def main():
    cs = ControlServer()
    cs.console_loop()
