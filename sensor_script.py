import asyncio
import struct
import sys
import os
from bleak import BleakClient, BleakScanner

# --- CONFIGURATION ---
LIMB_NAMES = ["Left_Arm", "Left_Leg", "Right_Arm", "Right_Leg"]

SENSORS = {
    "Left_Arm": "C9:CE:CE:5D:A9:BF", # Your known working sensor
    "Left_Leg": None,  
    "Right_Arm": None, 
    "Right_Leg": None  
}

# Global dictionary to hold the state of all 4 sensors
sensor_state = {
    name: {"roll": 0.0, "pitch": 0.0, "yaw": 0.0, "buffer": bytearray(), "connected": False}
    for name in LIMB_NAMES
}

# --- MEDICAL INTERPRETATION ---
def interpret_movement(limb_name, roll, pitch, yaw):
    """
    Translates raw IMU angles into doctor-friendly descriptions.
    Note: You may need to change 'pitch' to 'roll' or adjust the numbers (30, -30) 
    depending on exactly how the sensor is strapped to the patient.
    """
    status = "Resting / Neutral"
    
    if "Arm" in limb_name:
        # Assuming Pitch is forward/backward movement
        if pitch > 30.0:
            status = "Lifting Arm Up (Flexion)"
        elif pitch < -30.0:
            status = "Reaching Arm Back (Extension)"
        # Assuming Roll is twisting the arm
        elif roll > 45.0:
            status = "Arm Twisting Outward"
        elif roll < -45.0:
            status = "Arm Twisting Inward"
            
    elif "Leg" in limb_name:
        # Assuming Pitch is lifting the knee
        if pitch > 30.0:
            status = "Lifting Knee Up (Flexion)"
        elif pitch < -20.0:
            status = "Extending Leg Back"
        # Assuming Roll is twisting the leg
        elif roll > 30.0:
            status = "Leg Turned Outward"
        elif roll < -30.0:
            status = "Leg Turned Inward"

    return status

# --- AUTO-DISCOVERY SCANNER ---
async def discover_witmotion_sensors():
    print("\n" + "="*50)
    print(" 📡 SCANNING ROOM FOR ALL 4 SENSORS... (Please wait 5s)")
    print("="*50)
    
    devices = await BleakScanner.discover(timeout=5.0)
    found_addresses = []
    
    for d in devices:
        is_witmotion = False
        if d.name and any(x in d.name.upper() for x in ["WT", "BWT", "HC-08", "JDY"]):
            is_witmotion = True
        if d.address == "C9:CE:CE:5D:A9:BF":
            is_witmotion = True

        if is_witmotion and d.address not in found_addresses:
            found_addresses.append(d.address)
            print(f"✅ FOUND SENSOR: {d.address} | Name: {d.name}")

    print(f"\nTotal sensors found: {len(found_addresses)}")
    return found_addresses

# --- DATA PROCESSING ---
def process_data_for_sensor(sensor_name, packet: bytearray):
    state = sensor_state[sensor_name]
    ax, ay, az, wx, wy, wz, roll, pitch, yaw = struct.unpack('<hhhhhhhhh', packet[2:20])
    
    state["roll"] = roll / 32768.0 * 180.0
    state["pitch"] = pitch / 32768.0 * 180.0
    state["yaw"] = yaw / 32768.0 * 180.0

def make_notification_handler(sensor_name):
    """Creates a unique handler for each specific sensor."""
    def handler(sender, data):
        state = sensor_state[sensor_name]
        state["buffer"].extend(data)
        
        while len(state["buffer"]) >= 20:
            if state["buffer"][0] != 0x55:
                state["buffer"].pop(0) 
                continue
            if state["buffer"][1] == 0x61:
                packet = state["buffer"][:20]
                process_data_for_sensor(sensor_name, packet)
                state["buffer"] = state["buffer"][20:] 
            else:
                state["buffer"].pop(0)
    return handler

# --- INDIVIDUAL SENSOR CONNECTION TASK ---
async def connect_sensor(name, address):
    """Continuously tries to connect and stream data for a specific limb."""
    while True:
        try:
            async with BleakClient(address) as client:
                sensor_state[name]["connected"] = True# Dynamically find the notification channel
                notify_char = None
                for service in client.services:
                    for char in service.characteristics:
                        if "notify" in char.properties or "indicate" in char.properties:
                            notify_char = char.uuid
                            break
                    if notify_char: break
                
                if not notify_char:
                    notify_char = "0000ffe4-0000-1000-8000-00805f9b34fb" # Fallback
                
                await client.start_notify(notify_char, make_notification_handler(name))
                
                # Keep alive while connected
                while client.is_connected:
                    await asyncio.sleep(1)
                    
        except Exception:
            pass # Suppress error text so it doesn't break the terminal UI
        finally:
            sensor_state[name]["connected"] = False
            sensor_state[name]["buffer"].clear()
            await asyncio.sleep(3) # Wait 3 seconds before trying to reconnect

# --- TERMINAL DASHBOARD TASK ---
async def display_dashboard():
    """Prints a static, updating dashboard in the terminal."""
    print("\n" + "="*85)
    print(" 📊 LIVE IMU DASHBOARD (Press Ctrl+C to stop)")
    print("="*85)
    
    # Print empty lines to make room for the dashboard
    for _ in LIMB_NAMES:
        print()
        
    while True:
        # Move terminal cursor UP by the number of limbs
        print(f"\033[{len(LIMB_NAMES)}A", end="")
        
        for name in LIMB_NAMES:
            state = sensor_state[name]
            # \033[K clears the rest of the line so old numbers don't ghost
            if state["connected"]:
                r, p, y = state["roll"], state["pitch"], state["yaw"]
                
                # Get the doctor-friendly interpretation
                doctor_status = interpret_movement(name, r, p, y)
                
                # Print the raw data AND the doctor status
                print(f"\033[K 🟢 {name:>10} | Roll: {r:>7.2f}° | Pitch: {p:>7.2f}° | Yaw: {y:>7.2f}° | 🩺 {doctor_status}")
            else:
                print(f"\033[K 🔴 {name:>10} | Searching / Offline...")
                
        await asyncio.sleep(0.1) # Update dashboard 10 times a second

# --- MAIN EXECUTION ---
async def main():
    # 1. Scan the room
    discovered_addresses = await discover_witmotion_sensors()
    
    # 2. Assign unassigned MAC addresses to the limbs
    unassigned_macs = [addr for addr in discovered_addresses if addr not in SENSORS.values()]
    for name in LIMB_NAMES:
        if SENSORS[name] is None and unassigned_macs:
            SENSORS[name] = unassigned_macs.pop(0)

    # 3. Start the visual dashboard
    asyncio.create_task(display_dashboard())

    # 4. Start concurrent connections to all assigned sensors
    for name, address in SENSORS.items():
        if address:
            asyncio.create_task(connect_sensor(name, address))
            await asyncio.sleep(1.5) # Stagger connections slightly so Bluetooth doesn't choke
            
    # Keep the main program running forever
    while True:
        await asyncio.sleep(3600)

if name == "main":
    # Ensure terminal supports ANSI escape sequences (Windows fix)
    if os.name == 'nt':
        os.system('') 
        
    try: 
        asyncio.run(main())
    except KeyboardInterrupt: 
        print("\n\n⏹️ System safely shut down.")