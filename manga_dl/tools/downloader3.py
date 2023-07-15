# class Downloader:
#     def __init__(self, urls, headers=None, download_dir=None, check_exists=True, jpeg_compress=True, per_run:int=100):
#         """
#         Args:
#             urls (list): list of urls to download
#             headers (dict, optional): headers to use. Defaults to None.
#             download_dir (str, optional): directory to save downloaded files. Defaults to None.
#             check_exists (bool, optional): check if file already exists. Defaults to True.
#             jpeg_compress (bool, optional): compress downloaded files to jpeg. Defaults to True.
#             per_run (int, optional): number of files to download per run. Defaults to 100.
            
#         Usage:
#             >>> with Downloader(urls) as downloader:
#             >>>     doownloaded_files, failed_urls = downloader.download()

#         """
        
        
#         self.urls = urls
#         self.headers = headers or Headers().generate()
#         if headers is None:
#             self.headers["referer"] = "https://chapmanganato.com/"
            
#         self.download_dir:str = download_dir or os.environ.get("TEMP_DIR", "tmp")
#         if not os.path.exists(self.download_dir):
#             os.mkdir(self.download_dir)
        
#         self.check_exists = check_exists
#         self.jpeg_compress = jpeg_compress
#         self.per_run = per_run
        
#         self.progress = Manager().dict()
#         self.downloaded = Manager().list()
#         self.failed = Manager().list()
#         self.process_count = (os.cpu_count() or 2) * 2
#         self.current_progress = 0
#         self.total_urls = len(urls)
        
        
#         # async part
#         self.tasks = []
        
#     def share_progress_bar(
#         self, total_size: float, current_value: float, desc: str = ""):
#         # share with os.environ["PROGRESS_BAR"]
#         os.environ["PROGRESS_BAR"] = json.dumps(
#             {"total": total_size, "current": current_value, "desc": desc}
#         )
        
        
#     def download_file(self, url):
#         filename = get_file_name(url)
#         filepath = os.path.join(self.download_dir, filename)
        
#         if self.check_exists:
#             if os.path.exists(filepath):
#                 # self.update_progress(url, 1)
#                 self.downloaded.append(URLFile(url, filepath))
#                 return

#             if os.path.exists(compress_file_path(filepath)):
#                 # self.update_progress(url, 1)
#                 self.downloaded.append(URLFile(url, compress_file_path(filepath)))
#                 return
        
#         try:
#             filepath += ".tmp"
#             response = requests.get(url, headers=self.headers)
#             total_size = int(response.headers.get("Content-Length", 0))
#             block_size = 1024 * 1024
#             progress = 0
#             with open(filepath, "wb") as f:
#                 for chunk in response.iter_content(chunk_size=block_size):
#                     f.write(chunk)
#                     progress += len(chunk)
#                     self.update_progress(url, progress/total_size)
            
#             # download directly
#             # with open(filepath, "wb") as f:
#             #     f.write(response.content)

#             os.rename(filepath, filepath[:-4])
#             filepath = filepath[:-4]
            
#             if self.jpeg_compress:
#                 try:
#                     compressed_filepath = compress_file_path(filepath)
#                     compressed = jpeg_compress(open(filepath, "rb").read())
#                     with open(compressed_filepath, "wb") as f:
#                         f.write(compressed)
#                     os.remove(filepath)
#                     filepath = compressed_filepath
#                 except Exception as e:
#                     logger.error(f"Failed to compress {filepath} to jpeg", exc_info=True)
#                     logger.info("Saving without compression")
                    
#                 # self.update_progress(url, 1)
                
            
#             self.downloaded.append(URLFile(url, filepath))
#         except Exception as e:
#             logger.error(f"Failed to download {url}", exc_info=True)
#             self.failed.append(url)
            
            
            
#     async def adownload_file(self, url, session):
#         filename = get_file_name(url)
#         filepath = os.path.join(self.download_dir, filename)
        
#         if self.check_exists:
#             if os.path.exists(filepath):
#                 # self.update_progress(url, 1)
#                 self.downloaded.append(URLFile(url, filepath))
#                 return

#             if os.path.exists(compress_file_path(filepath)):
#                 # self.update_progress(url, 1)
#                 self.downloaded.append(URLFile(url, compress_file_path(filepath)))
#                 return
        
    
#     @staticmethod
#     def download_one(url, headers=None, download_dir=None, check_exists=True, jpg_compress=True) -> URLFile:
#         headers = headers or Headers().generate()
#         save_dir:str = download_dir or os.environ.get("TEMP_DIR", "tmp")
        
#         filename = get_file_name(url)
#         filepath = os.path.join(save_dir, filename)
#         cmp_filepath = compress_file_path(filepath)

#         if check_exists:
#             if os.path.exists(filepath):
#                 return URLFile(url, filepath)

#             if os.path.exists(cmp_filepath):
#                 return URLFile(url, cmp_filepath)
        
#         try:
#             response = requests.get(url, headers=headers)
#             total_size = int(response.headers.get("Content-Length", 0))
#             with open(filepath, "wb") as f:
#                 f.write(response.content)
            
#             if jpg_compress:
#                 try:
#                     compressed = jpeg_compress(open(filepath, "rb").read())
#                     with open(cmp_filepath, "wb") as f:
#                         f.write(compressed)
#                     os.remove(filepath)
#                     filepath = cmp_filepath
#                 except Exception as e:
#                     logger.error(f"Failed to compress {filepath} to jpeg", exc_info=True)
#                     logger.info("Saving without compression")
            
#             return URLFile(url, filepath)
        
#         except Exception as e:
#             logger.error(f"Failed to download {url}", exc_info=True)
#             filename = get_file_name(f"{url}-error")
#             filepath = os.path.join(save_dir, filename)
#             if not os.path.exists(filepath):
#                 failure_path = create_failure_image("error.png", filepath, url)
#                 filepath = failure_path
            
#             return URLFile(url, filepath)  
        

            
#     def update_progress(self, url, progress):
#         self.progress[url] = progress
    
    
#     def share_pbar(self, pbar, total_size):
#         self.current_progress += 1
#         pbar.update(1)
#         self.share_progress_bar(total_size, self.current_progress, desc="Downloading Files")
        
        
#     def run(self):
#         # chunks = [self.urls[i:i+self.per_run] for i in range(0, len(self.urls), self.per_run)]
#         total_size = len(self.urls)
        
#         with tqdm(total=len(self.urls),desc="Downloading Files") as pbar:
#             pbar.update(self.current_progress)
#             with Pool(self.process_count) as p:
#                 for url in self.urls:
#                     p.apply_async(self.download_file, args=(url,), callback=lambda _: self.share_pbar(pbar, total_size)) 
#                 p.close()
#                 p.join()
    
#     def download(self) -> tuple[list[URLFile], list[str]]:
#         self.run()
        
        
#         return list(self.downloaded), list(self.failed)
    
#     def clear(self):
#         self.downloaded = Manager().list()
#         self.failed = Manager().list()
#         self.progress = Manager().dict()
#         self.current_progress = 0
    
#     # enter and exit are used to make Downloader object usable in with statement
#     def __enter__(self):
#         return self
    
#     def __exit__(self, exc_type, exc_value, traceback):
#         self.clear()