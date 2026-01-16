#!/bin/bash
# Power optimization script for Raspberry Pi
# Reduces power consumption for battery-powered operation

set -e

ACTION="${1:-status}"

case "$ACTION" in
    enable)
        echo "Enabling power optimizations..."

        # Disable HDMI output
        if command -v tvservice &> /dev/null; then
            tvservice -o 2>/dev/null || true
        fi

        # Disable onboard LEDs (Pi Zero/3/4)
        echo none | sudo tee /sys/class/leds/led0/trigger 2>/dev/null || true
        echo 0 | sudo tee /sys/class/leds/led0/brightness 2>/dev/null || true
        echo none | sudo tee /sys/class/leds/led1/trigger 2>/dev/null || true
        echo 0 | sudo tee /sys/class/leds/led1/brightness 2>/dev/null || true

        # Set CPU governor to powersave
        for cpu in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
            echo powersave | sudo tee "$cpu" 2>/dev/null || true
        done

        # Disable USB if not needed (careful - may affect input devices)
        # Uncomment if you only use GPIO/I2C inputs:
        # echo '1-1' | sudo tee /sys/bus/usb/drivers/usb/unbind 2>/dev/null || true

        # Reduce GPU memory to minimum (requires reboot to take effect)
        # This is set in /boot/config.txt: gpu_mem=16

        echo "Power optimizations enabled"
        ;;

    disable)
        echo "Disabling power optimizations..."

        # Enable HDMI output
        if command -v tvservice &> /dev/null; then
            tvservice -p 2>/dev/null || true
            # Restore framebuffer
            fbset -depth 8 2>/dev/null || true
            fbset -depth 16 2>/dev/null || true
        fi

        # Restore LED defaults
        echo mmc0 | sudo tee /sys/class/leds/led0/trigger 2>/dev/null || true
        echo input | sudo tee /sys/class/leds/led1/trigger 2>/dev/null || true

        # Set CPU governor to performance mode (try multiple options)
        for cpu in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
            # Try governors in order of preference
            for gov in ondemand schedutil performance; do
                if grep -q "$gov" "${cpu%/*}/scaling_available_governors" 2>/dev/null; then
                    echo "$gov" | sudo tee "$cpu" 2>/dev/null && break
                fi
            done
        done

        echo "Power optimizations disabled"
        ;;

    status)
        echo "=== Power Status ==="

        # CPU governor
        gov=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null || echo "unknown")
        echo "CPU Governor: $gov"

        # CPU frequency
        freq=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq 2>/dev/null || echo "unknown")
        if [ "$freq" != "unknown" ]; then
            freq_mhz=$((freq / 1000))
            echo "CPU Frequency: ${freq_mhz} MHz"
        fi

        # LED status
        led0=$(cat /sys/class/leds/led0/trigger 2>/dev/null | grep -o '\[.*\]' | tr -d '[]' || echo "unknown")
        echo "LED0 Trigger: $led0"

        # WiFi status
        wifi_status=$(rfkill list wifi 2>/dev/null | grep -i "soft blocked" | head -1 || echo "unknown")
        echo "WiFi: $wifi_status"

        # Bluetooth status
        bt_status=$(rfkill list bluetooth 2>/dev/null | grep -i "soft blocked" | head -1 || echo "unknown")
        echo "Bluetooth: $bt_status"
        ;;

    *)
        echo "Usage: $0 {enable|disable|status}"
        exit 1
        ;;
esac
