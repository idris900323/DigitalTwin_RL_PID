"""dtrl: command-line interface for motor profiles, datasheet import, derivation, PID tuning and code export.

    python -m dtrl motor add --input datasheet.txt --id my_motor      guided import with mandatory confirmation
    python -m dtrl motor list | show <id> | derive --motor <id>
    python -m dtrl tune --motor <id> --load <load_id> [--out-dir DIR]
    python -m dtrl export --motor <id> --load <load_id> --format py|c|arduino [--out FILE]

Every recommendation is labelled with its tier and is PRELIMINARY until validated against hardware.
"""
