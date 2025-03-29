#!/bin/bash

# Usage: ./send_to_plotter.sh path/to/your/file.svg

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 path/to/your/file.svg"
    exit 1
fi

SVG_FILE="$1"
PI_USER="xbno"  # Change to your Pi username
PI_ADDRESS="plotterpi.local"  # Change to your Pi's hostname or IP
PI_DESTINATION="/home/xbno/plotterpi/svg/"  # Change to your desired directory
NEXTDRAW_CMD="source ~/plotterpi/venv/bin/activate && nextdraw"  # Adjust to your nextdraw location
# NEXTDRAW_CMD="$PI_DESTINATION/$(basename "$SVG_FILE") -q 3 -L 1"

# Transfer the file
echo "Transferring $SVG_FILE to Pi..."
scp "$SVG_FILE" $PI_USER@$PI_ADDRESS:$PI_DESTINATION

# Execute the plotting command
echo "Starting plot job..."
ssh $PI_USER@$PI_ADDRESS $NEXTDRAW_CMD $PI_DESTINATION/$(basename "$SVG_FILE") -q 3 -L 2 -Y

echo "Plot job submitted!"