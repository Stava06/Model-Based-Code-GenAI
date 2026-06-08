"""
    Messages module for the app server
    
    Includes:
        - start_mesaage : Starting a new function
        - success_message : A successful function
        - error_message : An error in a function
"""

def start_message(directory: str, action: str = None, variables: dict = {}) -> None:
    """
        Start message for starting a new function
        
        params:
            - directory: The directory of the function
            - action: The action of the function
            - variables: The variables of the function
    """
    directory = directory.capitalize()
    print(f" --------- Starting {directory} --------- ")
    print(f"Action: {action if action else 'None'}")
    print(f"Variables: {variables if variables else 'None'}\n")

def info_message(directory: str, message: str = "None") -> None:
    """
        Info message for the given directory
        
        params:
            - directory: The directory of the function
            - message: The message to print
    """
    directory = directory.capitalize()
    print(f" --> NOTE: {directory} <-- ")
    if message:
        print(f"Info: {message}\n")
    else:
        print()

def success_message(directory: str, message: str = None) -> None:
    """
        Success message for a successful function
        
        params:
            - directory: The directory of the function
            - message: The success message
    """
    directory = directory.capitalize()
    print(f" --------- SUCCESS in {directory} --------- ")
    if message:
        print(f"Message: {message}\n")
    else:
        print()

def error_message(directory: str, error: str = None) -> None:
    """
        Error message
        
        params:
            - directory: The directory of the function
            - error: The error message
    """
    directory = directory.capitalize()
    print(f" --------- ERROR in {directory} --------- ")
    if error:
        print(f"Error: {error}\n")
    else:
        print()
