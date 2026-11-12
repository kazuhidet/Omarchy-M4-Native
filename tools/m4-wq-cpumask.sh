#!/bin/sh
# SPDX-License-Identifier: MIT
# Keep unbound workqueues (writeback among them) off CPU 0 on an M4 Air (#132).
# Installed by omarchy-m4-speaker as /usr/lib/omarchy-m4/m4-wq-cpumask and run once,
# early in boot, by m4-wq-cpumask.service.
#
# Every device interrupt lands on CPU 0, and the speaker protection's period
# completion runs there. Background writeback can hold CPU 0 with preemption
# disabled for over 10 ms (wb->list_lock across move_expired_inodes), which ends
# protection with "J713 stale capture backlog/read". This writes "all possible CPUs
# but 0" to /sys/devices/virtual/workqueue/cpumask. Per-CPU work, interrupts and
# softirqs stay where they are. It lasts until the next boot; nothing else changes.
# Every refusal leaves the mask alone and exits 0, so it never fails the boot.
# M4_WQ_CPUMASK_ROOT prefixes the /sys and /proc paths (tests only).
set -eu
root=${M4_WQ_CPUMASK_ROOT:-}
mask_file=$root/sys/devices/virtual/workqueue/cpumask
compatible=$(tr '\0' '\n' 2>/dev/null < "$root/proc/device-tree/compatible" || true)
if ! printf '%s\n' "$compatible" | grep -qx 'apple,t8132'; then
  echo 'm4-wq-cpumask: not an M4 (apple,t8132); left unchanged'
  exit 0
fi
[ -w "$mask_file" ] || { echo "m4-wq-cpumask: $mask_file is not writable; left unchanged"; exit 0; }
possible=$(cat "$root/sys/devices/system/cpu/possible" 2>/dev/null || true)
# "0-9" or "0-3,6-7": set a bit for each possible CPU except 0.
mask=$(printf '%s\n' "$possible" | tr ',' '\n' | awk -F- '
  /^[0-9]+(-[0-9]+)?$/ { lo = $1 + 0; hi = (NF > 1) ? $2 + 0 : lo; seen = 1
                         for (c = lo; c <= hi; c++) if (c > 0) bit[c] = 1; if (hi > max) max = hi; next }
  NF { bad = 1 }
  END { if (bad || !seen) { print "bad"; exit } if (max > 62) { print "toolarge"; exit }
        m = 0; for (c in bit) m += 2 ^ c; printf "%x\n", m }')
case $mask in
  bad) echo "m4-wq-cpumask: cannot read the possible CPUs (${possible:-none}); left unchanged"; exit 0 ;;
  toolarge) echo 'm4-wq-cpumask: more than 63 CPUs; left unchanged'; exit 0 ;;
  0) echo 'm4-wq-cpumask: only CPU 0 is possible; left unchanged'; exit 0 ;;
esac
before=$(cat "$mask_file")
if ! echo "$mask" > "$mask_file" 2>/dev/null; then
  echo "m4-wq-cpumask: the kernel refused $mask; left at $before"
  exit 0
fi
after=$(cat "$mask_file")
if [ $((0x$(printf '%s' "$after" | tr -d ','))) -ne $((0x$mask)) ]; then
  echo "m4-wq-cpumask: wrote $mask but read back $after" >&2
  exit 1
fi
echo "m4-wq-cpumask: workqueue cpumask $before -> $after (CPU 0 excluded)"
