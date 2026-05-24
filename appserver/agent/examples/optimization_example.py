optimization_example = [
    "Add domain objects (Room, HVAC Unit, Temperature Sensor, Climate Controller, User Preference, Energy Mode, User), processes (Temperature Sensing, Comfort Evaluating, Heating Activating, Cooling Activating, HVAC Stopping, Eco Mode Applying, User Configuring), and attributes (Current Temperature, Desired Temperature) because the map only defines generic meta-OPL types.",
    "Add states for Room, HVAC Unit, and Energy Mode plus Effect Links with explicit from/to states for Comfort Evaluating, Heating Activating, Cooling Activating, HVAC Stopping, and Eco Mode Applying because OPL state transitions are not modeled.",
    "Replace generic Procedural Links with concrete Agent Links (Climate Controller, User) and Instrument Links (Temperature Sensor, HVAC Unit, Current Temperature, Desired Temperature, Energy Mode) because the OPL agent and instrument roles are missing.",
]
