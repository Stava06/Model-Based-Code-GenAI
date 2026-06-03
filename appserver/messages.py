"""
    Messages module for the app server
    
    Includes:
        - start_mesaage : Starting a new function
        - success_message : A successful function
        - error_message : An error in a function
"""


def start_message(directory: str, variables: dict = {}) -> None:
    """
        Start message for starting a new function
        
        params:
            - directory: The directory of the function
            - variables: The variables of the function
    """
    directory = directory.capitalize()
    print(f" --------- Starting {directory} --------- ")
    print(f"Variables: {variables if variables else 'None'}\n")

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
