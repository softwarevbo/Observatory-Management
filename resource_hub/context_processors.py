import shutil

def git_status(request):
    """
    Checks if Git is installed on the server's PATH.
    Returns a dictionary to make 'git_available' accessible in all templates.
    """
    return {
        'git_available': shutil.which('git') is not None
    }
