# Imports
from collections import defaultdict
from matplotlib import pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.transforms import Bbox
import os
import sys
import seaborn as sns
import statistics
import argparse
import subprocess

import matplotlib
matplotlib.rcParams['pdf.fonttype'] = 42
matplotlib.rcParams['ps.fonttype'] = 42

# Plot markers.
MARKERS = 'PXD*o^v<>.'

# Configure graph styling library.
sns.set_style('ticks')
font = {
    'font.weight': 1000,
    'font.size': 18,
}
sns.set_style(font)
paper_rc = {
    'lines.linewidth': 3,
    'lines.markersize': 10,
}
sns.set_context("paper", font_scale=3,  rc=paper_rc)
# plt.style.use('seaborn-v0_8-deep')
plt.style.use('seaborn-v0_8-white')

prop_cycle = plt.rcParams['axes.prop_cycle']
colors = prop_cycle.by_key()['color']
COLOR_MAP = defaultdict(lambda: None)
COLOR_MAP['quack'] = COLOR_MAP['quack_30ms_10'] = colors[0]
COLOR_MAP['pep'] = colors[2]
COLOR_MAP['quic'] = colors[1]
COLOR_MAP['tcp'] = colors[3]
COLOR_MAP['pep_h2'] = COLOR_MAP['pep']
COLOR_MAP['pep_r1'] = colors[4]

MAIN_RESULT_LABELS = ['Baseline', 'Sidekick', 'Sidekick(2x)', 'Sidekick(4x)']
MAIN_RESULT_ZORDERS = [2, 3, 1, 0]
MAIN_RESULT_COLORS = ['#ff7f0e', '#1f77b4', '#8ec3de', '#aab2bd']

# Bar graph hatches
HATCHES = ['/', '.', '\\\\', 'O']

# Line width
LINEWIDTH = 3

# Marker size
MARKERSIZE = 10

# Line styles
# https://matplotlib.org/stable/gallery/lines_bars_and_markers/linestyles.html
LINESTYLES = [
    (0, (3, 1, 1, 1)),  # densely dashdotted
    'solid',
    (0, (5, 1)),  # densely dashed
    (0, (1, 1, 3, 1, 3, 1, 3, 1)),  # densely dashdashdashdotted
    (0, (3, 1, 1, 1, 5, 1, 1, 1)),  # densely dashdotdashhhdotted
    (0, (1, 1)),  # densely dotted
]
LINESTYLE_MAP = {}
LINESTYLE_MAP['quic'] = LINESTYLES[0]
LINESTYLE_MAP['quack'] = LINESTYLES[1]
LINESTYLE_MAP['tcp'] = LINESTYLES[2]
LINESTYLE_MAP['pep'] = LINESTYLES[3]

styles = [
'Solarize_Light2', '_classic_test_patch', '_mpl-gallery', '_mpl-gallery-nogrid',
'bmh', 'classic', 'dark_background', 'fast', 'fivethirtyeight', 'ggplot',
'grayscale', 'seaborn-v0_8', 'seaborn-v0_8-bright', 'seaborn-v0_8-colorblind',
'seaborn-v0_8-dark', 'seaborn-v0_8-dark-palette', 'seaborn-v0_8-darkgrid',
'seaborn-v0_8-deep', 'seaborn-v0_8-muted', 'seaborn-v0_8-notebook',
'seaborn-v0_8-paper', 'seaborn-v0_8-pastel', 'seaborn-v0_8-poster',
'seaborn-v0_8-talk', 'seaborn-v0_8-ticks', 'seaborn-v0_8-white',
'seaborn-v0_8-whitegrid', 'tableau-colorblind10']

def save_pdf(output_filename, bbox_inches='tight'):
    if output_filename is not None:
        with PdfPages(output_filename) as pdf:
            pdf.savefig(bbox_inches=bbox_inches)
    print(output_filename)

def time_to_tput(total_time, n):
    """
    Converts runtime (in seconds) to throughput (in Mbit/s) where the data size
    is provided as a string <data_size>M in MBytes.
    """
    assert n[-1] == 'M'
    n = int(n[:-1])
    return n * 8 / total_time

LABEL_MAP = {}
LABEL_MAP['quic'] = 'QUIC E2E'
LABEL_MAP['quack'] = 'QUIC+Sidekick'
LABEL_MAP['tcp'] = 'TCP E2E'
LABEL_MAP['pep'] = 'TCP+PEP'
LABEL_MAP['pep_r1'] = 'TCP+PEP(proxy)'
LABEL_MAP['pep_h2'] = 'TCP+PEP'
LABEL_MAP['quack-2ms-r'] = LABEL_MAP['quack']
LABEL_MAP['quack-2ms-rm'] = LABEL_MAP['quack']
LABEL_MAP['quack_30ms_10'] = LABEL_MAP['quack']

FONTSIZE = 18

class DataPoint:
    def __init__(self, arr, normalize=None):
        if normalize is not None:
            arr = [normalize * 1. / x for x in arr]
        arr.sort()
        mid = int(len(arr) / 2)
        self.p50 = statistics.median(arr)
        if len(arr) % 2 == 1:
            self.p25 = statistics.median(arr[:mid+1])
        else:
            self.p25 = statistics.median(arr[:mid])
        self.p75 = statistics.median(arr[mid:])
        self.minval = arr[0]
        self.maxval = arr[-1]
        self.avg = statistics.mean(arr)
        self.stdev = None if len(arr) == 1 else statistics.stdev(arr)

DEFAULT_SIDEKICK_HOME = os.environ['HOME'] + '/sidekick'
parser = argparse.ArgumentParser()
parser.add_argument('--execute', action='store_true',
                    help='Execute benchmarks for missing data points')
parser.add_argument('--workdir',
                    default=DEFAULT_SIDEKICK_HOME,
                    help='Working directory (default: $HOME/sidekick)')
parser.add_argument('--outdir',
                    default=f'{DEFAULT_SIDEKICK_HOME}/figures/output',
                    help='Output directory for plots (default: $HOME/sidekick/figures/output)')
parser.add_argument('--logdir',
                    default=f'{DEFAULT_SIDEKICK_HOME}/results',
                    help='Log directory for data (default: $HOME/sidekick/results)')
parser.add_argument('--legend', type=int, default=1,
                    help='Whether to plot a legend [0|1]. (default: 1)')

def execute_experiment(cmd, filename, cwd=DEFAULT_SIDEKICK_HOME):
    print(' '.join(cmd))
    p = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, env=dict(os.environ, RUST_LOG='warn'))
    with open(filename, 'ab') as f:
        f.write(' '.join(cmd).encode('utf-8'))
        f.write(b'\n')
        for line in p.stdout:
            sys.stdout.buffer.write(line)
            sys.stdout.buffer.flush()
            f.write(line)
    p.wait()
