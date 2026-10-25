$env:PYTHONPATH = "$PSScriptRoot\src;" + $env:PYTHONPATH
python -m signalroom.cli $args
