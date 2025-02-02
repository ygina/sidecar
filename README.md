# Sidekick

<p align="center">
  <img alt="The data sender sends packets using an opaque base protocol to the data receiver. The middlebox, which is on the path, sends quACKs via the sidekick protocol to the data sender" src="/img/model.png" width="500" />
</p>

Sidekick protocols are a method for in-network assistance of opaque transport
protocols that leaves the transport protocol unmodified on the wire and free
to evolve. The sidekick protocol is spoken on an adjacent connection between
an end host and a PEP. Sidekick PEPs report their observations on packets in
the base connection, and end hosts use this information to influence decisions
about how and when to send or resend packets, approximating some of the
performance benefits of traditional PEPs.

The repository is organized as follows:

```
deps/               # scripts for building and installing dependencies
figures/            # scripts for running/graphing experiments in the NSDI '24 paper
http3_integration/  # HTTP/3 file upload client integration
|__curl/
|__quiche/
media_integration/  # low-latency media client integration
mininet/            # two-hop network emulation environment
quack/              # library and microbenchmarks for the quack data structure
sidekick/           # sidekick binary implementations for middleboxes
visualizer/         # web visualizer for sidekick-related quiche debug logs
```

## Getting Started

To reproduce the experiments in the NSDI '24 paper,
_[Sidekick: In-Network Assistance for Secure End-to-End Transport Protocols](https://ginayuan.com/papers/nsdi24-sidekick.pdf)_,
first build and install all dependencies according to the instructions
[here](https://github.com/ygina/sidekick/tree/main/deps).
Our experiments were run on an m4.xlarge AWS instance with a 4-CPU Intel Xeon
E5 processor and 16 GB memory, running Ubuntu 22.04, but it should be possible
to adapt the instructions for any x86_64 Linux machine. (These experiments have also
been tested on a [CloudLab](https://cloudlab.us/) d710 node running Ubuntu 22.04.)
Each figure in the paper has
a corresponding script, and the instructions can be found
[here](https://github.com/ygina/sidekick/tree/main/figures).

For a more minimal installation, install [Rust](https://www.rust-lang.org/tools/install)
and [mininet](https://mininet.org/download/). Build the media server and client
using `cargo build --release` and run the low-latency media experiment in
emulation using `python figures/fig4b_low_latency_media.py --execute -t 1`.
You may need to install some Python and other system dependencies as well.

## BibTeX

```
TODO
```

## Quacknowledgements

This work was supported in part by NSF grants 2045714, 2039070, 2028733, 1931750, 1918056, 1763256,
and DGE1656518, DARPA contract HR001120C0107, a Stanford Graduate Fellowship, a Sloan Research
Fellowship, and by Google, VMware, Dropbox, Amazon, and Meta Platforms.

