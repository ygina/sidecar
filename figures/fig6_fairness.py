import os
import re
import statistics
from collections import defaultdict
from common import *

TARGET_XS = {}
TARGET_XS['pep'] = [x for x in range(0, 1050, 50)]
TARGET_XS['quack_pacubic'] = [x for x in range(0, 1050, 50)]
TARGET_XS['quack'] = [x for x in range(0, 850, 50)]
TARGET_XS['quic'] = [0, 25, 50, 100, 150, 200, 300, 400, 500]
TARGET_XS['tcp'] = [0, 25, 50, 100, 150, 200, 300, 400, 500, 600, 700, 800]

def collect_ys_mean(ys, n):
    assert n[-1] == 'M'
    n_megabit = int(n[:-1]) * 1.0 * 8.0
    ys = [n_megabit * 8 / y for y in ys]
    y = statistics.mean(ys)
    yerr = 0 if len(ys) == 1 else statistics.stdev(ys)
    return (y, yerr)

def collect_ys_median(ys, n):
    assert n[-1] == 'M'
    n_megabit = int(n[:-1]) * 1.0 * 8.0
    ys = [n_megabit / y for y in ys]
    ys.sort()
    y = statistics.median(ys)
    mid = int(len(ys) / 2)
    if len(ys) % 2 == 1:
        p25 = statistics.median(ys[:mid+1])
    else:
        p25 = statistics.median(ys[:mid])
    p75 = statistics.median(ys[mid:])
    yerr = (y-p25, p75-y)
    return (y, yerr)

def parse_data(filename, key, trials, max_x, far_loss, data_key='time_total'):
    loss = None
    key_index = None
    exitcode_index = None
    data = defaultdict(lambda: [])

    with open(filename) as f:
        lines = f.read().split('\n')
    for line in lines:
        line = line.strip()

        # Get the current loss percentage in hundredths of a percent
        if far_loss:
            m = re.search(r'Link1.*loss=(\S+) .*', line)
        else:
            m = re.search(r'Link2.*loss=(\S+) .*', line)
        if m is not None:
            loss = round(float(m.group(1)) * 100.0)
            continue

        # Figure out which index to parse the total time and exitcode
        if data_key in line:
            keys = line.split()
            for i in range(len(keys)):
                if keys[i] == data_key:
                    key_index = i
                elif keys[i] == 'exitcode':
                    exitcode_index = i
            continue
        if key_index is None:
            continue

        # Either we're done with this loss percentage or read another data point
        if line == '' or '***' in line or '/tmp' in line or 'No' in line or \
            'factor' in line or 'unaccounted' in line or 'sudo' in line:
            key_index = None
            exitcode_index = None
            pass
        else:
            line = line.split()
            if len(line) < exitcode_index:
                key_index = None
                exitcode_index = None
                continue
            if '[sidekick]' in line:
                continue
            try:
                if exitcode_index is not None and int(line[exitcode_index]) != 0:
                    continue
            except:
                key_index = None
                exitcode_index = None
                continue
            data[loss].append(float(line[key_index]))

    xs = [x for x in filter(lambda x: x <= max_x, TARGET_XS[key])]
    xs.sort()
    ys = [data[x][:min(len(data[x]), trials)] for x in xs]
    return (xs, ys)

def maybe_collect_missing_data(filename, key, args):
    (xs, ys) = parse_data(filename, key, args.trials, args.max_x, args.far_loss)

    missing_losses = []
    for i in range(len(xs)):
        missing = max(0, args.trials - len(ys[i]))
        loss = f'{xs[i]*0.01:.2f}'
        if missing == args.trials:
            missing_losses.append(loss)
        elif missing > 0:
            print(f'{loss}% {len(ys[i])}/{args.trials} {filename}')
    if len(missing_losses) > 0:
        print('missing', missing_losses)

    if not args.execute:
        return
    for i in range(len(xs)):
        missing = max(0, args.trials - len(ys[i]))
        loss = f'{xs[i]*0.01:.2f}'
        if missing == 0:
            continue
        cmd = ['sudo', '-E', 'python3', 'mininet/main.py', '-n', args.n,
               '--bw1', str(args.bw1), '--bw2', str(args.bw2), '-t', str(missing),
               '--stderr', 'loss_tput.error', '--timeout', '120']
        if args.far_loss:
            cmd += ['--loss1', loss, '--loss2', '0']
        else:
            cmd += ['--loss1', '0', '--loss2', loss]
        cmd += ['--delay1', str(args.delay1), '--delay2', str(args.delay2)]
        cmd += ['--frequency', args.frequency, '--threshold', str(args.threshold)]
        cmd += args.args
        if 'quack' in key:
            cmd += ['quack']
        else:
            cmd += [key]
        execute_experiment(cmd, filename, cwd=args.workdir)

def plot_graph(args, data, https, legend, pdf=None):
    max_x = 0
    plt.figure(figsize=(15, 5))
    for (i, key) in enumerate(https):
        (xs, ys, yerr) = data[key]
        if key in LABEL_MAP:
            label = LABEL_MAP[key]
        else:
            label = key
        color = None if key not in COLOR_MAP else COLOR_MAP[key]
        plt.errorbar(xs, ys, yerr=yerr, marker=MARKERS[i], markersize=MARKERSIZE*1.5,
                     label=label, color=color, linewidth=LINEWIDTH,
                     capsize=5, linestyle=LINESTYLES[i], elinewidth=2)
        if len(xs) > 0:
            max_x = max(max_x, max(xs))
    plt.xlabel(f'Loss % (Link 1 Delay = {args.delay2} ms, Link 2 Delay = {args.delay1} ms)')
    plt.ylabel('Goodput (Mbit/s)')
    plt.xlim(0, max_x)
    plt.ylim(0)
    plt.grid()
    if legend:
        plt.legend(loc='upper center', bbox_to_anchor=(0.5, 1.3), ncol=4)
    # plt.title(pdf)
    if pdf:
        save_pdf(f'{args.outdir}/{pdf}')

def plot_legend(args, data, https, pdf):
    pdf = f'{args.outdir}/{pdf}'
    plot_graph(args, data, https, legend=False)
    plt.legend(loc='upper center', bbox_to_anchor=(0.5, 1.3), ncol=4, frameon=True)
    bbox = Bbox.from_bounds(0.5, 4.55, 14.35, 0.95)
    save_pdf(pdf, bbox_inches=bbox)

if __name__ == '__main__':
    DEFAULT_PROTOCOLS = ['quic', 'quack', 'tcp', 'pep', 'quack_pacubic']

    parser.add_argument('-n', default='10M',
        help='data size (default: 10M)')
    parser.add_argument('--http', action='extend', nargs='+', default=[],
        help=f'HTTP versions. (default: {DEFAULT_PROTOCOLS})')
    parser.add_argument('-t', '--trials', default=10, type=int,
        help='number of trials per data point (default: 10)')
    parser.add_argument('--bw1', default=10, type=int,
        help='bandwidth of far path segment in Mbps (default: 10)')
    parser.add_argument('--bw2', default=100, type=int,
        help='bandwidth of near path segment in Mbps (default: 100)')
    parser.add_argument('--max-x', default=800, type=int,
        help='maximum loss perecentage in hundredths of a percentage (default: 800)')
    parser.add_argument('--delay1', default=25, type=int,
        help='in ms (default: 25)')
    parser.add_argument('--delay2', default=1, type=int,
        help='in ms (default: 1)')
    parser.add_argument('--frequency', default='30ms',
        help='in ms (default: 30ms)')
    parser.add_argument('--threshold', default=10, type=int,
        help='in number of packets (default: 10)')
    parser.add_argument('--args', action='extend', nargs='+', default=[],
        help='additional arguments to append to the mininet/main.py command if executing.')
    parser.add_argument('--mean', action='store_true',
        help='use the mean instead of the median')
    parser.add_argument('--far-loss', action='store_true',
        help='vary loss on the far path segment instead of the near one')
    args = parser.parse_args()

    # Create the directory that holds the results.
    https = DEFAULT_PROTOCOLS if len(args.http) == 0 else args.http
    path = f'{args.logdir}/loss_tput/bw{args.bw2}/{args.n}/{args.delay1}ms_{args.delay2}ms'
    os.system(f'mkdir -p {path}')

    # Parse results data, and collect missing data points if specified.
    data = {}
    for key in https:
        filename = f'{path}/{key}.txt'
        print(filename)
        os.system(f'touch {filename}')
        maybe_collect_missing_data(filename, key, args)
        (xs, ys) = parse_data(filename, key, args.trials, args.max_x, args.far_loss)
        new_xs = []
        new_ys = []
        if args.mean:
            new_yerrs = []
        else:
            new_yerrs = ([], [])
        for i in range(len(ys)):
            if len(ys[i]) == 0:
                continue
            new_xs.append(0.01*xs[i])
            if args.mean:
                (collected_ys, yerr) = collect_ys_mean(ys[i], args.n)
                new_ys.append(collected_ys)
                new_yerrs.append(yerr)
            else:
                (collected_ys, yerr) = collect_ys_median(ys[i], args.n)
                new_ys.append(collected_ys)
                new_yerrs[0].append(yerr[0])
                new_yerrs[1].append(yerr[1])
        data[key] = (new_xs, new_ys, new_yerrs)

    # Plot data.
    pdf = f'fig6_loss_bw{args.bw2}_{args.n}_delay_{args.delay1}ms_{args.delay2}ms.pdf'
    plot_graph(args, data, https, args.legend, pdf=pdf)
    plot_legend(args, data, https, pdf='fig6_legend.pdf')
