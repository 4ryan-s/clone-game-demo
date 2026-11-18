#!/bin/sh
# The CUDA wheels keep their libraries inside site-packages. ONNX Runtime only
# finds them when those directories are on the linker path before it starts.
LIBS=$(python -c 'import glob, site
paths = []
for base in site.getsitepackages():
    paths.extend(glob.glob(base + "/nvidia/*/lib"))
print(":".join(paths))')
if [ -n "$LIBS" ]; then
  export LD_LIBRARY_PATH="${LIBS}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi
exec "$@"
