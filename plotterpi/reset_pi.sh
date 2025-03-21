#!/bin/bash

# Usage: ./reset_pi.sh

PI_USER="xbno"  # Change to your Pi username
PI_ADDRESS="plotterpi.local"  # Change to your Pi's hostname or IP
PI_DESTINATION="/home/xbno/plotterpi/svg/"  # Change to your desired directory
NEXTDRAW_CMD="source ~/plotterpi/venv/bin/activate && nextdraw"  # Adjust to your nextdraw location
# NEXTDRAW_CMD="$PI_DESTINATION/$(basename "$SVG_FILE") -q 3 -L 1"

# Transfer the file
# echo "Transferring $SVG_FILE to Pi..."
# scp "$SVG_FILE" $PI_USER@$PI_ADDRESS:$PI_DESTINATION

# Execute the plotting command if walk_home argument provided
if [ "$1" = "walk_home" ]; then
    echo "Starting plot job..."
    ssh $PI_USER@$PI_ADDRESS "source ~/plotterpi/venv/bin/activate && nextdraw -m utility -M walk_home"
fi

# Execute the plotting command if walk_y argument provided
if [ "$1" = "walk_y" ]; then
    echo "Starting plot job..."
    ssh $PI_USER@$PI_ADDRESS "source ~/plotterpi/venv/bin/activate && nextdraw -m utility -M walk_y -w $2"
fi

# Execute the plotting command if walk_x argument provided
if [ "$1" = "walk_x" ]; then
    echo "Starting plot job..."
    ssh $PI_USER@$PI_ADDRESS "source ~/plotterpi/venv/bin/activate && nextdraw -m utility -M walk_x -w $2"
fi

# Execute the plotting command if raise_pen argument provided
if [ "$1" = "raise_pen" ]; then
    echo "Starting plot job..."
    ssh $PI_USER@$PI_ADDRESS "source ~/plotterpi/venv/bin/activate && nextdraw -m utility -M raise_pen"
fi

# Execute the plotting command if lower_pen argument provided
if [ "$1" = "lower_pen" ]; then
    echo "Starting plot job..."
    ssh $PI_USER@$PI_ADDRESS "source ~/plotterpi/venv/bin/activate && nextdraw -m utility -M lower_pen"
fi

echo "Done!"