import time
import json
import traceback

from oct_turrets.base import BaseTurret
from oct_turrets.canon import Canon


class Turret(BaseTurret):
    """This class represent the classic turret for oct
    """

    def init_commands(self):
        """Initialize the basics commandes for the turret
        """
        self.commands['start'] = self.run
        self.commands['status_request'] = self.send_status

    def send_status(self, msg=None):
        """Reply to the master by sending the current status
        """
        if not self.already_responded:
            print("responding to master")
            reply = self.build_status_message()
            self.result_collector.send_json(reply)
            self.already_responded = True

    def send_result(self, result):
        """Update the results and send it to the hq
        """
        result['turret_name'] = self.config['name']
        self.result_collector.send_json(result)

    def start(self):
        """Start the turret and wait for the master to run the test
        """
        print("starting turret")
        self.status = "Ready"
        self.send_status()
        while self.start_loop:
            payload = self.master_publisher.recv_string()
            payload = json.loads(payload)
            self.exec_command(payload)

    def run(self, msg=None):
        """The main run method
        """
        print("Starting tests")

        self.start_time = time.time()
        self.start_loop = False
        self.status = 'running'
        self.send_status()

        if 'rampup' in self.config:
            rampup = float(self.config['rampup']) / float(self.config['canons'])
        else:
            rampup = 0

        last_insert = 0

        if rampup > 0 and rampup < 1:
            timeout = rampup * 1000
        else:
            timeout = 1000

        try:
            while self.run_loop:
                if len(self.canons) < self.config['canons'] and time.time() - last_insert >= rampup:
                    canon = Canon(self.start_time, self.script_module, self.uuid)
                    canon.daemon = True
                    self.canons.append(canon)
                    canon.start()
                    last_insert = time.time()

                socks = dict(self.poller.poll(timeout))
                if self.master_publisher in socks:
                    data = self.master_publisher.recv_string()
                    data = json.loads(data)
                    if 'command' in data and data['command'] == 'stop':  # not managed, must break the loop
                        print("Exiting loop, premature stop")
                        self.run_loop = False
                        break
                if self.local_result in socks:
                    results = self.local_result.recv_json()
                    self.send_result(results)

            print("Sending stop signal to canons...")
            for i in self.canons:
                i.run_loop = False
            print("Waiting for all canons to finish")
            for i in self.canons:
                i.join()
            print("Turret shutdown")

        except (Exception, RuntimeError, KeyboardInterrupt) as e:
            self.status = "Aborted"
            print(e)
            self.send_status()
            traceback.print_exc()
            # data = self.build_status_message()
            # self.result_collector.send_json(data)
            # self.start_loop = True
            # self.already_responded = False

    def stop(self, msg=None):
        """The main stop method
        """
        pass
