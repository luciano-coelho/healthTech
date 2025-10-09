import os


class CleanupFileMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # if 'File-Path' in response:
        #     file_path = response['File-Path']
        #     if os.path.exists(file_path):
        #         os.remove(file_path)
        
        return response