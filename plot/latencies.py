import argparse
import subprocess
import os
import re
import sys
import os.path
import statistics
import math
from os import path
from collections import defaultdict
from common import *

WORKDIR = os.environ['HOME'] + '/sidecar'

def plot_graph(data, keys, legend=True, pdf=None):
    plt.figure(figsize=(9, 2))
    for (i, key) in enumerate(keys):
        ys = [y / 1000000.0 for y in data[key]]
        plt.plot(range(101), ys, marker=MARKERS[i], label=key)
    plt.xlabel('Percentile')
    plt.ylabel('Latency (ms)')
    plt.xlim(0, 100)
    plt.ylim(0)
    if legend:
        plt.legend(loc='upper center', bbox_to_anchor=(0.5, 1.8), ncol=2)
    plt.title(pdf)
    if pdf:
        save_pdf(f'{WORKDIR}/plot/graphs/{pdf}')
    plt.clf()

if __name__ == '__main__':
    data = {}
    keys = ['base_loss1', 'quack_loss1_freq19ms']
    # keys += ['base_loss10', 'quack_loss10_freq20ms']
    data['base_loss1'] = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 13019159, 32442532, 52598017, 72855292, 92872845, 113088289, 133182839, 152555689]
    data['base_loss10'] = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 12071625, 12223073, 13089241, 32151668, 32256333, 32351614, 33259203, 52297331, 52400903, 52514110, 52575809, 71627423, 72427185, 72568345, 72677660, 72713662, 91791780, 91817737, 91942029, 92786273, 92821809, 93021003, 111948634, 111984252, 112069136, 112090391, 112933331, 112985412, 125076431, 132105265, 132207011, 132222096, 132237894, 132268316, 133156865, 152337121, 152353566, 152359315, 152367358, 152371263, 152381893, 152397022, 152416960, 172325228, 172656502, 191904652, 204902971, 212051176, 232043276, 232300646, 252173693, 252384804, 272339933, 272582052, 291740321, 292693624, 311870113, 312833912, 332988162, 372545070, 431935188, 472369756, 532996842, 612708734, 792415139]
    data['quack_loss1_freq15ms'] = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 15321163]
    data['quack_loss1_freq19ms'] = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 19248287]
    data['quack_loss1_freq20ms'] = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3991917, 4091838, 4956121, 4975895, 4988555, 5009217, 5011281, 5052052, 5089611, 15154229, 15175043]
    data['quack_loss10_freq20ms'] = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 4121921, 4315239, 5004513, 5019362, 5026590, 5034487, 5077427, 5199125, 15296679, 54856115]
    pdf = f'latencies_webrtc.pdf'
    plot_graph(data, keys=keys, pdf=pdf)
