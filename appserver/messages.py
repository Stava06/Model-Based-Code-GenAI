import time
TIME = None

def start_message(directory: str, variables: dict = {}):
    directory = directory.capitalize()
    print(f" --------- Starting {directory} --------- ")
    print(f"Variables: {variables if variables else 'None'}\n")

    global TIME
    TIME = time.time()

def success_message(directory: str, message: str = None):
    directory = directory.capitalize()
    print(f" --------- SUCCESS in {directory} --------- ")
    if message:
        print(f"Message: {message}\n")
    print(f"Time taken: {round(time.time() - TIME, 2)} seconds\n")

def error_message(directory: str, error: str):
    directory = directory.capitalize()
    print(f" --------- ERROR in {directory} --------- ")
    print(f"Error: {error}\n")
