import argparse
import logging
import sys
import time
from mininet.net import Mininet
from mininet.cli import CLI
from mininet.log import setLogLevel
from mininet.link import TCLink

def mac(digit):
    assert 0 <= digit < 10
    return '00:00:00:00:00:0{}'.format(int(digit))

def ip(digit):
    assert 0 <= digit < 10
    return '10.0.{}.10/24'.format(int(digit))

def sclog(val):
    print('[sidecar] {}'.format(val), file=sys.stderr);

class SidecarNetwork():
    def __init__(self, args):
        self.net=None
        self.pep = args.pep
        self.delay1 = '{}ms'.format(int(args.delay1))
        self.delay2 = '{}ms'.format(int(args.delay2))
        self.loss1 = int(args.loss1)
        self.loss2 = int(args.loss2)
        self.bw1 = int(args.bw1)
        self.bw2 = int(args.bw2)
        if args.cc not in ['reno', 'cubic']:
            sclog('invalid congestion control algorithm: {}'.format(args.cc))
        self.cc = args.cc

    def start_and_configure(self):
        self.net = Mininet(controller=None, link=TCLink)

        # Add hosts and switches
        self.h1 = self.net.addHost('h1', ip=ip(1), mac=mac(1))
        self.h2 = self.net.addHost('h2', ip=ip(2), mac=mac(2))
        self.r1 = self.net.addHost('r1')

        # Add links
        self.net.addLink(self.r1, self.h1, bw=self.bw1, delay=self.delay1, loss=self.loss1)
        self.net.addLink(self.r1, self.h2, bw=self.bw2, delay=self.delay2, loss=self.loss2)
        self.net.build()

        # Configure interfaces
        self.r1.cmd("ifconfig r1-eth0 0")
        self.r1.cmd("ifconfig r1-eth1 0")
        self.r1.cmd("ifconfig r1-eth0 hw ether 00:00:00:00:01:01")
        self.r1.cmd("ifconfig r1-eth1 hw ether 00:00:00:00:01:02")
        self.r1.cmd("ip addr add 10.0.1.1/24 brd + dev r1-eth0")
        self.r1.cmd("ip addr add 10.0.2.1/24 brd + dev r1-eth1")
        self.r1.cmd("echo 1 > /proc/sys/net/ipv4/ip_forward")
        self.h1.cmd("ip route add default via 10.0.1.1")
        self.h2.cmd("ip route add default via 10.0.2.1")

        # Configure link latency and delay
        # self.h1.cmd('tc qdisc add dev h1-eth0 root netem delay {}ms'.format(self.delay1))
        # self.r1.cmd('tc qdisc add dev r1-eth1 root netem delay {}ms'.format(self.delay2))
        # # r1 <-- h2
        # h2_cmd = 'tc qdisc add dev h2-eth0 root netem delay {}ms'.format(self.delay2)
        # if self.loss2 > 0:
        #     h2_cmd += ' loss {}%'.format(self.loss2)
        # print(h2_cmd)
        # self.h2.cmd(h2_cmd)
        # # h1 <-- r1
        # r1_cmd = 'tc qdisc add dev r1-eth0 root netem delay {}ms'.format(self.delay1)
        # if self.loss1 > 0:
        #     r1_cmd += ' loss {}%'.format(self.loss1)
        # self.r1.cmd(r1_cmd)

        # Set the TCP congestion control algorithm
        sclog('Setting congestion control to {}'.format(self.cc))
        cc_cmd = 'sysctl -w net.ipv4.tcp_congestion_control={}'.format(self.cc)
        self.h1.cmd(cc_cmd)
        self.r1.cmd(cc_cmd)
        self.h2.cmd(cc_cmd)

        # Start the webserver on h1
        # TODO: not user-dependent path
        sclog('Starting the NGINX/Python webserver on h1...')
        self.h1.cmd("nginx -c /home/gina/sidecar/webserver/nginx.conf")
        self.h1.cmd("python3 webserver/server.py &")

        # Start the TCP PEP on r1
        if self.pep:
            sclog('Starting the TCP PEP on r1...')
            self.r1.cmd('ip rule add fwmark 1 lookup 100')
            self.r1.cmd('ip route add local 0.0.0.0/0 dev lo table 100')
            self.r1.cmd('iptables -t mangle -F')
            self.r1.cmd('iptables -t mangle -A PREROUTING -i r1-eth1 -p tcp -j TPROXY --on-port 5000 --tproxy-mark 1')
            self.r1.cmd('iptables -t mangle -A PREROUTING -i r1-eth0 -p tcp -j TPROXY --on-port 5000 --tproxy-mark 1')
            self.r1.cmd('pepsal -v &')
        else:
            sclog('NOT starting the TCP PEP')

    def benchmark(self, nbytes, http_version, trials, cc):
        """
        Args:
        - nbytes: Number of bytes to send e.g., 1M.
        - http_version:
            HTTP/1.1 - http/1.1 1.1 1 h1 tcp
            HTTP/3.3 - http/3 3 h3 quic
        - trials
        """
        if http_version is None:
            sclog('must set http version: {}'.format(http_version))
            return
        http_version = http_version.lower()
        if http_version in ['http/1.1', '1.1', '1', 'h1', 'tcp']:
            http_version = 1
        elif http_version in ['http/3', '3', 'h3', 'quic']:
            http_version = 3
        else:
            sclog('must set http version: {}'.format(http_version))
            return

        try:
            trials = int(trials)
        except:
            sclog('`trials` must be a number: {}'.format(trials))
            return

        self.start_and_configure()
        time.sleep(1)
        self.h2.cmdPrint('./webserver/run_client.sh {} {} {} {}'.format(
            nbytes, http_version, trials, self.cc))

    def cli(self):
        CLI(self.net)

    def stop(self):
        if self.net is not None:
            self.net.stop()


if __name__ == '__main__':
    setLogLevel('info')

    parser = argparse.ArgumentParser(prog='Sidecar')
    parser.add_argument('--benchmark',
                        metavar='HTTP_VER',
                        help='Run a single benchmark rather than start the '
                             'CLI for the HTTP version [tcp|quic]')
    parser.add_argument('-p', '--pep', action='store_true',
                        help='Start a TCP pep on r1')
    parser.add_argument('-cc',
                        default='cubic',
                        metavar='TCP_CC_ALG',
                        help='Sets the TCP and QUIC congestion control '
                             'mechanism [reno|cubic] (default: cubic)')
    parser.add_argument('--delay1',
                        default=75,
                        metavar='MS',
                        help='1/2 RTT between h1 and r1 (default: 75)')
    parser.add_argument('--delay2',
                        default=1,
                        metavar='MS',
                        help='1/2 RTT between r1 and h2 (default: 1)')
    parser.add_argument('--loss1',
                        default=0,
                        metavar='num',
                        help='loss (in %%) between h1 and r1 (default: 0)')
    parser.add_argument('--loss2',
                        default=1,
                        metavar='num',
                        help='loss (in %%) between r1 and h2 (default: 1)')
    parser.add_argument('--bw1',
                        default=sys.maxsize,
                        help='link bandwidth (in Mbps) between h1 and r1 '
                             '(default: unlimited)')
    parser.add_argument('--bw2',
                        default=sys.maxsize,
                        help='link bandwidth (in Mbps) between r1 and h2 '
                             '(default: unlimited)')
    parser.add_argument('-s', '--sidecar', action='store_true',
                        help='If benchmark, enables the sidecar')
    parser.add_argument('-n', '--nbytes',
                        default='100k',
                        metavar='num',
                        help='If benchmark, the number of bytes to run '
                        '(default: 100k)')
    parser.add_argument('-t', '--trials',
                        default=1,
                        metavar='num',
                        help='If benchmark, the number of trials (default: 1)')
    args = parser.parse_args()
    sc = SidecarNetwork(args)

    if args.benchmark is not None:
        sc.benchmark(args.nbytes, args.benchmark, args.trials, args.cc)
        sc.stop()
    else:
        sc.start_and_configure()
        sc.cli()
        sc.stop()
