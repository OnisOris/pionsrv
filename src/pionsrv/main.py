from pionsrv.control_server import ControlServer


def main():
    control_server = ControlServer(broadcast_port=37020)
    control_server.console_loop()


if __name__ == "__main__":
    main()
