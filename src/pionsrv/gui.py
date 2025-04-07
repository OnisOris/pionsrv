import curses
import threading
import time
import numpy as np
from pion import Pion  # Импортируем библиотеку для управления дроном

# Отключаем экспоненциальное представление numpy
np.set_printoptions(suppress=True)

def scan_network():
    """
    Функция-симулятор сканирования сети.
    В реальном приложении здесь можно реализовать пинг или рассылку UDP-сообщений.
    """
    # Для демонстрации возвращаем статический список IP-адресов
    return ["10.1.100.101", "10.1.100.102", "10.1.100.103"]

class DroneController:
    """
    Обёртка для управления дроном с использованием Pion.
    В конструкторе создаётся экземпляр Pion с заданным IP.
    """
    def __init__(self, ip):
        self.ip = ip
        self.drone = Pion(ip=ip, mavlink_port=5656, logger=True, dt=0., count_of_checking_points=5)
        self.led_thread = None
        self.track_thread = None
        self.stop_led_event = threading.Event()
        self.stop_track_event = threading.Event()

    def led_continuous(self):
        """Запускает LED в режиме continuous (-c)"""
        self.drone.led_control(255, 0, 255, 0)
        self.drone.logger = True
        while not self.stop_led_event.is_set():
            time.sleep(0.02)

    def start_led_continuous(self):
        self.stop_led_event.clear()
        self.led_thread = threading.Thread(target=self.led_continuous)
        self.led_thread.daemon = True
        self.led_thread.start()

    def stop_led_continuous(self):
        self.stop_led_event.set()
        if self.led_thread:
            self.led_thread.join()

    def land_command(self):
        """Команда -l: LED, посадка, задержка и disarm"""
        self.drone.led_control(255, 0, 0, 0)
        self.drone.land()
        time.sleep(10)
        self.drone.disarm()

    def disarm_command(self):
        """Команда -d: LED, disarm, LED"""
        self.drone.led_control(255, 255, 0, 0)
        self.drone.disarm()
        self.drone.led_control(255, 0, 0, 0)

    def arm_takeoff(self):
        """Команда -at: LED, arm, takeoff"""
        self.drone.led_control(255, 255, 0, 0)
        self.drone.arm()
        self.drone.takeoff()

    def reboot_command(self):
        """Команда -r: Перезагрузка платы"""
        self.drone.reboot_board()

    def track_command(self):
        """Команда -tr: arm, takeoff, задержка, старт track point, затем цикл (запускается в отдельном потоке)"""
        self.drone.arm()
        self.drone.takeoff()
        time.sleep(8)
        self.drone.start_track_point()
        while not self.stop_track_event.is_set():
            time.sleep(1)

    def start_track(self):
        self.stop_track_event.clear()
        self.track_thread = threading.Thread(target=self.track_command)
        self.track_thread.daemon = True
        self.track_thread.start()

    def goto_yaw(self, yaw):
        """Если в параметрах указана команда 'yaw'"""
        self.drone.goto_yaw(yaw)

    def default_command(self, x, y, z, yaw):
        """
        Действие по умолчанию:
          arm, takeoff, задержка, set_v, goto_from_outside, stop, land.
        """
        self.drone.arm()
        self.drone.takeoff()
        time.sleep(8)
        self.drone.set_v()
        self.drone.goto_from_outside(x, y, z, yaw)
        self.drone.stop()
        self.drone.land()

class CursesInterface:
    """
    Интерфейс на базе curses:
      - Главное меню с возможностью сканирования сети, выбора IP дрона и выполнения команд.
      - При выборе команды запрашиваются необходимые параметры.
    """
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.selected_ip = None
        self.drone_controller = None
        self.log_lines = []

    def add_log(self, msg):
        self.log_lines.append(msg)
        if len(self.log_lines) > 100:
            self.log_lines = self.log_lines[-100:]

    def draw_logs(self, log_win):
        log_win.clear()
        height, width = log_win.getmaxyx()
        start_line = max(0, len(self.log_lines) - height)
        for idx, line in enumerate(self.log_lines[start_line:]):
            try:
                log_win.addstr(idx, 0, line[:width-1])
            except curses.error:
                pass
        log_win.refresh()

    def main_menu(self):
        menu = ["Сканировать сеть", "Выбрать дрон", "Выполнить команду", "Выход"]
        current_selection = 0
        while True:
            self.stdscr.clear()
            self.stdscr.addstr(0, 0, "Главное меню:")
            for idx, item in enumerate(menu):
                if idx == current_selection:
                    self.stdscr.addstr(idx+1, 2, "> " + item)
                else:
                    self.stdscr.addstr(idx+1, 2, "  " + item)
            self.stdscr.refresh()
            key = self.stdscr.getch()
            if key == curses.KEY_UP and current_selection > 0:
                current_selection -= 1
            elif key == curses.KEY_DOWN and current_selection < len(menu)-1:
                current_selection += 1
            elif key == ord("\n"):
                if menu[current_selection] == "Сканировать сеть":
                    self.scan_network()
                elif menu[current_selection] == "Выбрать дрон":
                    self.select_drone()
                elif menu[current_selection] == "Выполнить команду":
                    self.command_menu()
                elif menu[current_selection] == "Выход":
                    break

    def scan_network(self):
        self.add_log("Сканирование сети...")
        ips = scan_network()
        self.add_log("Найденные IP: " + ", ".join(ips))
        self.available_ips = ips

    def select_drone(self):
        if not hasattr(self, "available_ips") or not self.available_ips:
            self.add_log("Сначала выполните сканирование сети!")
            return
        current_selection = 0
        while True:
            self.stdscr.clear()
            self.stdscr.addstr(0, 0, "Выберите дрон:")
            for idx, ip in enumerate(self.available_ips):
                if idx == current_selection:
                    self.stdscr.addstr(idx+1, 2, "> " + ip)
                else:
                    self.stdscr.addstr(idx+1, 2, "  " + ip)
            self.stdscr.addstr(len(self.available_ips)+2, 0, "Нажмите Enter для выбора, ESC для возврата")
            self.stdscr.refresh()
            key = self.stdscr.getch()
            if key == curses.KEY_UP and current_selection > 0:
                current_selection -= 1
            elif key == curses.KEY_DOWN and current_selection < len(self.available_ips)-1:
                current_selection += 1
            elif key == 27:  # ESC
                break
            elif key == ord("\n"):
                self.selected_ip = self.available_ips[current_selection]
                self.add_log(f"Выбран дрон: {self.selected_ip}")
                self.drone_controller = DroneController(self.selected_ip)
                break

    def command_menu(self):
        if not self.drone_controller:
            self.add_log("Сначала выберите дрон!")
            return
        commands = [
            "LED Continuous (-c)",
            "Land (-l)",
            "Disarm (-d)",
            "Arm+Takeoff (-at)",
            "Reboot (-r)",
            "Track (-tr)",
            "Goto Yaw (yaw)",
            "Default Command",
            "Вернуться"
        ]
        current_selection = 0
        while True:
            self.stdscr.clear()
            self.stdscr.addstr(0, 0, f"Команды для дрона {self.selected_ip}:")
            for idx, cmd in enumerate(commands):
                if idx == current_selection:
                    self.stdscr.addstr(idx+1, 2, "> " + cmd)
                else:
                    self.stdscr.addstr(idx+1, 2, "  " + cmd)
            self.stdscr.refresh()
            key = self.stdscr.getch()
            if key == curses.KEY_UP and current_selection > 0:
                current_selection -= 1
            elif key == curses.KEY_DOWN and current_selection < len(commands)-1:
                current_selection += 1
            elif key == ord("\n"):
                selected_cmd = commands[current_selection]
                if selected_cmd == "Вернуться":
                    break
                self.execute_command(selected_cmd)
                self.stdscr.addstr(len(commands)+2, 0, "Нажмите любую клавишу для продолжения...")
                self.stdscr.getch()

    def prompt_input(self, prompt):
        curses.echo()
        self.stdscr.clear()
        self.stdscr.addstr(0, 0, prompt)
        self.stdscr.refresh()
        input_str = self.stdscr.getstr(1, 0, 60).decode("utf-8")
        curses.noecho()
        return input_str

    def execute_command(self, cmd):
        self.add_log(f"Выполнение команды: {cmd}")
        if cmd.startswith("LED Continuous"):
            # Запуск LED в отдельном потоке
            self.drone_controller.start_led_continuous()
            self.add_log("LED Continuous запущен. Нажмите любую клавишу для остановки.")
            self.stdscr.getch()
            self.drone_controller.stop_led_continuous()
            self.add_log("LED Continuous остановлен.")
        elif cmd.startswith("Land"):
            self.drone_controller.land_command()
            self.add_log("Команда land выполнена.")
        elif cmd.startswith("Disarm"):
            self.drone_controller.disarm_command()
            self.add_log("Команда disarm выполнена.")
        elif cmd.startswith("Arm+Takeoff"):
            self.drone_controller.arm_takeoff()
            self.add_log("Команда arm+takeoff выполнена.")
        elif cmd.startswith("Reboot"):
            self.drone_controller.reboot_command()
            self.add_log("Команда reboot выполнена.")
        elif cmd.startswith("Track"):
            self.drone_controller.start_track()
            self.add_log("Команда track запущена. Нажмите любую клавишу для остановки.")
            self.stdscr.getch()
            self.drone_controller.stop_track_event.set()
            if self.drone_controller.track_thread:
                self.drone_controller.track_thread.join()
            self.add_log("Track остановлен.")
        elif cmd.startswith("Goto Yaw"):
            yaw_str = self.prompt_input("Введите значение yaw:")
            try:
                yaw = float(yaw_str)
                self.drone_controller.goto_yaw(yaw)
                self.add_log(f"Команда goto_yaw выполнена с yaw={yaw}.")
            except ValueError:
                self.add_log("Неверное значение yaw.")
        elif cmd.startswith("Default Command"):
            x_str = self.prompt_input("Введите x:")
            y_str = self.prompt_input("Введите y:")
            z_str = self.prompt_input("Введите z:")
            yaw_str = self.prompt_input("Введите yaw:")
            try:
                x = float(x_str)
                y = float(y_str)
                z = float(z_str)
                yaw = float(yaw_str)
                self.drone_controller.default_command(x, y, z, yaw)
                self.add_log("Default Command выполнена.")
            except ValueError:
                self.add_log("Неверные параметры для Default Command.")
        else:
            self.add_log("Неизвестная команда.")

def main(stdscr):
    interface = CursesInterface(stdscr)
    interface.main_menu()

if __name__ == "__main__":
    curses.wrapper(main)
