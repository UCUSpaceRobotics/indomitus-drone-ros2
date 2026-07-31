# Composite Video Output Test

This script shows the live downward-camera image on the Raspberry Pi display stack so the signal can be routed to composite output.

## What it does

- Opens the downward camera
- Sends raw frames to the display sink
- Uses the existing `src/cv/display.py` module
- Runs fullscreen by default
- Lets you quit with `q` or `Esc`

## Requirements

- Raspberry Pi desktop session running for user `erso`
- Composite output enabled in the Pi display configuration
- `.venv` created in the repository root
- OpenCV installed with GUI support in the virtualenv

## Recommended launch

From the repository root:

```bash
chmod +x scripts/run_composite_output.sh
./scripts/run_composite_output.sh
```

## Manual launch

If you want to run the Python script directly:

```bash
sudo -u erso env DISPLAY=:0 XAUTHORITY=/home/erso/.Xauthority QT_QPA_PLATFORM=xcb \
  ./.venv/bin/python scripts/test_composite_output.py --backend picamera2 --device-index 0
```

## Notes

- The wrapper is needed because SSH does not inherit the graphical session.
- The script opens the display through the active desktop session, which is then shown on composite output.
- If you only want to confirm camera capture without display, use `--disabled`.