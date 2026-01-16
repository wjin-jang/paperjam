#!/bin/bash
# WiFi control script for on-demand WiFi usage
# Saves power by keeping WiFi off when not needed

set -e

ACTION="${1:-status}"
TIMEOUT="${2:-15}"

case "$ACTION" in
    enable)
        # Unblock WiFi
        sudo rfkill unblock wifi 2>/dev/null || true

        # Bring interface up
        sudo ip link set wlan0 up 2>/dev/null || true

        # Wait for connection (up to TIMEOUT seconds)
        count=0
        while [ $count -lt $TIMEOUT ]; do
            # Check if we have an IP address
            ip_addr=$(ip -4 addr show wlan0 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -1)
            if [ -n "$ip_addr" ]; then
                echo "connected:$ip_addr"
                exit 0
            fi
            sleep 1
            count=$((count + 1))
        done

        echo "timeout"
        exit 1
        ;;

    disable)
        # Bring interface down
        sudo ip link set wlan0 down 2>/dev/null || true

        # Block WiFi radio
        sudo rfkill block wifi 2>/dev/null || true

        echo "disabled"
        ;;

    status)
        # Check if WiFi is blocked
        blocked=$(rfkill list wifi 2>/dev/null | grep -i "soft blocked: yes" && echo "yes" || echo "no")

        if [ "$blocked" = "yes" ]; then
            echo "disabled"
            exit 0
        fi

        # Check if connected
        ip_addr=$(ip -4 addr show wlan0 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -1)
        if [ -n "$ip_addr" ]; then
            echo "connected:$ip_addr"
        else
            echo "disconnected"
        fi
        ;;

    *)
        echo "Usage: $0 {enable|disable|status} [timeout_seconds]"
        exit 1
        ;;
esac
