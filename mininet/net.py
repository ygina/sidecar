import argparse
import logging
import sys
import time
import client
import re
import os
import subprocess
from mininet.net import Mininet
from mininet.cli import CLI
from mininet.log import setLogLevel
from mininet.link import TCLink

SLEEP_S = 0.1

def mac(digit):
    assert 0 <= digit < 10
    return f'00:00:00:00:00:0{int(digit)}'

def ip(digit):
    assert 0 <= digit < 10
    return f'10.0.{int(digit)}.10/24'

def sclog(val):
    print(f'[sidecar] {val}', file=sys.stderr);

def get_max_queue_size_bytes(rtt_ms, bw_mbps):
    bdp = rtt_ms * bw_mbps * 1000000. / 1000. / 8.
    return bdp

def get_max_queue_size(rtt_ms, bw_mbps):
    """
    Calculate the maximum queue size as
    Bandwidth Delay Product (BDP) / MTU * 1.1 packets.
    """
    bdp = rtt_ms * bw_mbps * 1000000. / 1000. / 8.
    mtu = 1500
    return int(bdp / mtu * 1.1) + 1

class SidecarNetwork():
    def __init__(self, args):
        self.net=None
        self.pep = args.pep
        self.sidecar = args.sidecar
        self.threshold = args.threshold
        self.delay1 = args.delay1
        self.delay2 = args.delay2
        self.loss1 = args.loss1
        self.loss2 = float(args.loss2) if '.' in args.loss2 else int(args.loss2)
        self.bw1 = args.bw1
        self.bw2 = args.bw2
        self.log_level = args.log_level
        if args.pep and args.sidecar is not None:
            sclog('only one of the PEP or sidecar can be enabled')
            exit()
        if args.cc not in ['reno', 'cubic']:
            sclog(f'invalid congestion control algorithm: {args.cc}')
            exit()
        self.cc = args.cc
        self.tso = args.tso

    def clean_logs(self):
        os.system('rm -f r1.log h1.log h2.log f1.log f2.log')

    def start_webserver(self):
        # Start the webserver on h1
        # TODO: not user-dependent path
        sclog('Starting the NGINX/Python webserver on h1...')
        self.h1.cmd("kill $(pidof nginx)")
        self.h1.cmd("nginx -c /home/gina/sidecar/webserver/nginx.conf")
        self.h1.cmd("python3 webserver/server.py >> h1.log 2>&1 &")

    def start_tcp_pep(self):
        # Start the TCP PEP on r1
        sclog('Starting the TCP PEP on r1...')
        self.r1.cmd('ip rule add fwmark 1 lookup 100')
        self.r1.cmd('ip route add local 0.0.0.0/0 dev lo table 100')
        self.r1.cmd('iptables -t mangle -F')
        self.r1.cmd('iptables -t mangle -A PREROUTING -i r1-eth1 -p tcp -j TPROXY --on-port 5000 --tproxy-mark 1')
        self.r1.cmd('iptables -t mangle -A PREROUTING -i r1-eth0 -p tcp -j TPROXY --on-port 5000 --tproxy-mark 1')
        self.r1.cmd('pepsal -v >> r1.log 2>&1 &')

    def start_quack_sender(self):
        # Start the quACK sender on r1
        print('', file=sys.stderr)
        sclog('Starting the QUIC sidecar sender on r1...')
        assert self.sidecar is not None
        if 'ms' in self.sidecar:
            frequency = re.match(r'(\d+)ms', self.sidecar).group(1)
            frequency = f'--frequency-ms {frequency}'
        elif 'p' in self.sidecar:
            frequency = re.match(r'(\d+)p.*', self.sidecar).group(1)
            frequency = f'--frequency-pkts {frequency}'
        else:
            raise 'Invalid frequency: {}'.format(self.sidecar)

        self.r1.cmd(f'kill $(pidof sidecar)')
        self.r1.cmd(f'RUST_BACKTRACE=1 RUST_LOG={self.log_level} ' \
            f'./target/release/sidecar -i r1-eth1 -t {self.threshold} ' + \
            f'quack-sender --target-addr 10.0.2.10:5103 ' + \
            f'{frequency} >> r1.log 2>&1 &')

    def start_and_configure(self):
        self.net = Mininet(controller=None, link=TCLink)

        # Add hosts and switches
        self.h1 = self.net.addHost('h1', ip=ip(1), mac=mac(1))
        self.h2 = self.net.addHost('h2', ip=ip(2), mac=mac(2))
        self.r1 = self.net.addHost('r1')

        # Add links
        rtt_ms = 2 * (self.delay1 + self.delay2)
        bw_mbps = min(self.bw1, self.bw2)
        self.net.addLink(self.r1, self.h1)
        self.net.addLink(self.r1, self.h2)
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

        # Configure link latency, delay, bandwidth, and queue size
        # https://unix.stackexchange.com/questions/100785/bucket-size-in-tbf
        mqs = get_max_queue_size_bytes(rtt_ms, bw_mbps)
        print(f'max_queue_size (bytes) = {mqs}')
        def tc(host, iface, loss, delay, bw, queue_size):
            host.cmd(f'tc qdisc add dev {iface} root handle 1:0 '+\
                     f'netem loss {loss}% delay {delay}ms')
            host.cmd(f'tc qdisc add dev {iface} parent 1:1 handle 10: '+\
                     f'tbf rate {bw}mbit burst {bw*500*2} limit {queue_size}')
        tc(self.h1, 'h1-eth0', self.loss1, self.delay1, self.bw1, mqs)
        tc(self.r1, 'r1-eth0', self.loss1, self.delay1, self.bw1, mqs)
        tc(self.r1, 'r1-eth1', self.loss2, self.delay2, self.bw2, mqs)
        tc(self.h2, 'h2-eth0', self.loss2, self.delay2, self.bw2, mqs)

        # Set the TCP congestion control algorithm
        sclog(f'Setting congestion control to {self.cc}')
        cc_cmd = f'sysctl -w net.ipv4.tcp_congestion_control={self.cc}'
        self.h1.cmd(cc_cmd)
        self.r1.cmd(cc_cmd)
        self.h2.cmd(cc_cmd)

        # Don't cache TCP metrics
        tcp_metrics_cmd = 'echo 1 > /proc/sys/net/ipv4/tcp_no_metrics_save'
        self.h1.cmd(tcp_metrics_cmd)
        self.r1.cmd(tcp_metrics_cmd)
        self.h2.cmd(tcp_metrics_cmd)

        # Turn off tso and gso to send MTU-sized packets
        sclog('tso and gso are {}'.format('ON' if self.tso else 'OFF'))
        if not self.tso:
            self.h1.cmd('ethtool -K h1-eth0 gso off tso off')
            self.h2.cmd('ethtool -K h2-eth0 gso off tso off')
            self.r1.cmd('ethtool -K r1-eth0 gso off tso off')
            self.r1.cmd('ethtool -K r1-eth1 gso off tso off')

        self.start_webserver()
        if self.pep:
            self.start_tcp_pep()
        if self.sidecar is not None:
            self.start_quack_sender()

    def iperf(self, time_s):
        self.start_and_configure()
        self.h1.cmd('iperf3 -s -f m > /dev/null 2>&1 &')
        self.h2.cmdPrint(f'iperf3 -c 10.0.1.10 -t {time_s} -f m -b 20M -C cubic -i 0.1')

    def multiflow(self, f1, f2, delay):
        """
        o = currently possible
        x = needs to be implemented
        - = impossible

              pep quack quic tcp
        pep   o   o     o    -
        quack -   x     o    o
        quic  -   -     o    o
        tcp   -   -     -    o
        """
        assert args.nbytes is not None
        assert not (f1 == 'quack' and f2 == 'quack')
        assert not (f1 == 'tcp' and f2 == 'pep')
        assert not (f1 == 'pep' and f2 == 'tcp')
        if 'pep' in [f1, f2]:
            self.pep = True
        if 'quack' in [f1, f2]:
            self.sidecar = '2ms'
        self.start_and_configure()

        def make_cmd(bm):
            if bm in ['tcp', 'pep']:
                http_version = 1
            elif bm in ['quic', 'quack']:
                http_version = 3
            elif bm == 'null':
                return 'echo ""'
            else:
                raise f'invalid benchmark: {bm}'
            cmd = ['python3', 'mininet/client.py', '-n', args.nbytes,
                   '--http', str(http_version),
                   '--stdout', args.stdout, '--stderr', args.stderr,
                   '-cc', self.cc, '--loss', str(self.loss2), '-t', '1']
            if bm == 'quack':
                cmd += ['-s', 'h2-eth0', str(self.threshold), '--quack-reset']
            return cmd

        f1_cmd = make_cmd(f1)
        f2_cmd = make_cmd(f2)

        home_dir = os.environ['HOME']
        prefix = f'{home_dir}/sidecar/results/multiflow/loss{self.loss2}p'
        pcap_file = f'{prefix}/{f1}_{f2}_{args.nbytes}_delay{args.delay}s.pcap'
        os.system(f'mkdir -p {prefix}')
        os.system(f'rm -f {pcap_file}')
        self.h1.cmd(f"tcpdump -w {pcap_file} -i h1-eth0 'ip src 10.0.2.10 and (tcp or udp)' &")
        p1 = self.h2.popen(f1_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        time.sleep(args.delay)
        p2 = self.h2.popen(f2_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        def wait(p, logfile, i, bm):
            with open(logfile, 'ab') as f:
                for line in p.stdout:
                    f.write(line)
                    if b'200' in line:
                        sys.stdout.buffer.write(line.strip())
                        sys.stdout.buffer.write(
                            bytes(f'\t\t(flow{i}={bm})\n', 'utf-8'))
                        sys.stdout.buffer.flush()
                    if b'time_total' in line and b'sidecurl' not in line:
                        sys.stdout.buffer.write(line)
                        sys.stdout.buffer.flush()
            p.wait()

        wait(p1, 'f1.log', 1, f1)
        wait(p2, 'f2.log', 2, f2)
        print(pcap_file)


    def benchmark(self, args):
        if args.benchmark is None:
            sclog(f'must set http version: {args.benchmark}')
            return
        http_version = args.benchmark.lower()
        if http_version in ['http/1.1', '1.1', '1', 'h1', 'tcp']:
            http_version = 1
        elif http_version in ['http/3', '3', 'h3', 'quic']:
            http_version = 3
        else:
            sclog(f'must set http version: {http_version}')
            return

        h2_cmd = f'python3 mininet/client.py -n {args.nbytes} ' \
                 f'--http {http_version} ' \
                 f'--stdout {args.stdout} --stderr {args.stderr} ' \
                 f'-cc {self.cc} --loss {self.loss2} ' \
                 f'--log-level {self.log_level} '
        if self.sidecar is not None:
            h2_cmd += f'--sidecar h2-eth0 {self.threshold} '
        if args.trials is None:
            trials = 1
        else:
            trials = args.trials
            h2_cmd += f'-t {trials} ' if self.sidecar is None else '-t 1 '

        # Add flags
        if args.quack_reset:
            h2_cmd += '--quack-reset '
        if args.sidecar_mtu:
            h2_cmd += '--sidecar-mtu '
        if args.quack_log:
            h2_cmd += ' > h2.log'

        self.start_and_configure()
        time.sleep(SLEEP_S)

        if self.sidecar is not None:
            self.h2.cmdPrint(h2_cmd)
            for _ in range(trials - 1):
                self.start_quack_sender()
                time.sleep(SLEEP_S)
                self.h2.cmdPrint(h2_cmd)
        else:
            self.h2.cmdPrint(h2_cmd)

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
    parser.add_argument('--tso', action='store_true',
                        help='Enable TCP segment offloading (tso) and generic '
                             'segment offloading (gso). By default, both are '
                             'disabled')
    parser.add_argument('-cc',
                        default='cubic',
                        metavar='TCP_CC_ALG',
                        help='Sets the TCP and QUIC congestion control '
                             'mechanism [reno|cubic] (default: cubic)')
    parser.add_argument('--log-level',
                        default='error',
                        help='Sets the RUST_LOG level in the quACK sender '
                             '(if applicable) and the quiche client. '
                             '[error|warn|info|debug|trace] (default: error)')
    parser.add_argument('--delay1',
                        type=int,
                        default=75,
                        metavar='MS',
                        help='1/2 RTT between h1 and r1 (default: 75)')
    parser.add_argument('--delay2',
                        type=int,
                        default=1,
                        metavar='MS',
                        help='1/2 RTT between r1 and h2 (default: 1)')
    parser.add_argument('--loss1',
                        type=int,
                        default=0,
                        metavar='num',
                        help='loss (in %%) between h1 and r1 (default: 0)')
    parser.add_argument('--loss2',
                        type=str,
                        default='1',
                        metavar='num',
                        help='loss (in %%) between r1 and h2 (default: 1)')
    parser.add_argument('--bw1',
                        type=int,
                        default=10,
                        help='link bandwidth (in Mbps) between h1 and r1 '
                             '(default: 10)')
    parser.add_argument('--bw2',
                        type=int,
                        default=100,
                        help='link bandwidth (in Mbps) between r1 and h2 '
                             '(default: 100)')
    parser.add_argument('-s', '--sidecar',
                        help='If benchmark, enables the sidecar and sends '
                             'the quACK with the specified frequency. '
                             'Units are in terms of ms or packets e.g., '
                             '2ms or 2p')
    parser.add_argument('--threshold',
                        type=int,
                        default=20,
                        help='If benchmark, sets the quACK sender and '
                             'receiver to initialize their quACKs with '
                             'this threshold.')
    parser.add_argument('-n', '--nbytes',
                        default='1M',
                        metavar='num',
                        help='If benchmark, the number of bytes to run '
                        '(default: 1M)')
    parser.add_argument('-t', '--trials',
                        type=int,
                        metavar='num',
                        help='If benchmark, the number of trials')
    parser.add_argument('--stdout',
                        default='/dev/null',
                        metavar='FILENAME',
                        help='If benchmark, file to write curl stdout '
                             '(default: /dev/null)')
    parser.add_argument('--stderr',
                        default='/dev/null',
                        metavar='FILENAME',
                        help='If benchmark, file to write curl stderr '
                             '(default: /dev/null)')
    parser.add_argument('--iperf',
                        type=int,
                        metavar='TIME_S',
                        help='Run an iperf test for this length of time with '
                             'a server on h1 and client on h2.')
    parser.add_argument('--quack-log', action='store_true')
    parser.add_argument('--sidecar-mtu', action='store_true',
                        help='Send packets only if cwnd > mtu')
    parser.add_argument('--quack-reset', action='store_true',
                        help='Whether to send quack reset messages')

    subparsers = parser.add_subparsers(title='subcommands')
    mf = subparsers.add_parser('multiflow', help='run two flows simultaneously')
    mf.add_argument('-f1', '--flow1', required=True,
                    help='[quack|quic|tcp|pep]')
    mf.add_argument('-f2', '--flow2', required=True,
                    help='[quack|quic|tcp|pep]')
    mf.add_argument('-d', '--delay', default=0, type=int,
                    help='delay in starting flow2, in s (default: 0)')

    args = parser.parse_args()
    sc = SidecarNetwork(args)
    sc.clean_logs()

    if args.iperf is not None:
        sc.iperf(args.iperf)
    elif hasattr(args, 'flow1') and hasattr(args, 'flow2'):
        sc.multiflow(args.flow1, args.flow2, args.delay)
    elif args.benchmark is not None:
        sc.benchmark(args)
    else:
        sc.start_and_configure()
        sc.cli()
    sc.stop()
