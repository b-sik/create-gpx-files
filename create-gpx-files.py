import os
import requests
import csv
import time
import urllib.parse
import pathlib
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

load_dotenv()

gpx_dir = "../gpx"
dl_dir = os.path.join(pathlib.Path.home(), "Downloads")

options = webdriver.FirefoxOptions()
options.set_preference("browser.download.folderList", 2)
options.set_preference("browser.download.dir", gpx_dir)
options.set_preference(
    "browser.helperApps.neverAsk.saveToDisk", "application/octet-stream"
)
options.set_preference("browser.download.manager.showWhenStarting", False)


def main():
    driver = webdriver.Firefox()

    get_server_redirected_urls()
    get_client_redirected_urls(driver)
    create_gps_vis_urls()
    get_all_gpx(driver)
    
    driver.quit()


def get_server_redirected_urls():
    """
    Many of the provided links are shortened urls without readable gps information.
    This lets each url redirect to the final url provided by the server.
    """
    with open("original_map_urls.csv", 'r', newline="") as map_urls_file, open("server_redirected_urls.csv", 'w', newline="") as server_redirected_file:
        reader = csv.reader(map_urls_file, delimiter=",")
        writer = csv.writer(server_redirected_file)
        
        headers = next(reader)  # skip header
        writer.writerow(headers)

        for row in reader:
            response = make_request(row[1])
            if response.history:
                writer.writerow([row[0], response.url])
            else:
                writer.writerow(row)
                

def get_client_redirected_urls(driver):
    """
    This gets the final gmaps url that redirects clientside and has usable gps data.
    """
    with open("server_redirected_urls.csv", "r", newline="") as server_redirected_file, open("client_redirected_urls.csv", "w", newline="") as client_redirected_urls:
        reader = csv.reader(server_redirected_file, delimiter=",")
        writer = csv.writer(client_redirected_urls)
        
        headers = next(reader)  # skip header
        writer.writerow(headers)

        for row in reader:
            try:
                # wait for '/dir/' to appear in url to indicate it has redirected.
                driver.get(row[1])
                redirected_url = WebDriverWait(driver, 10).until(EC.url_contains("/dir/"))
                final_url = driver.execute_script("return window.location.href")

                writer.writerow([row[0], final_url])
            except:
                writer.writerow(row)
            finally:
                print(row[0] + ": " + url_dict[row[0]] + "\n")
                


def create_gps_vis_urls():
    """
    Create encoded urls to download gpx files from.
    """
    with open("client_redirected_urls.csv", "r", newline="") as client_redirected_urls, open("gps_vis_urls.csv", "w", newline="") as gps_vis_urls:
        reader = csv.reader(client_redirected_urls, delimiter=",")
        writer = csv.writer(gps_vis_url)
        
        headers = next(url_reader) # skip header
        writer.writerow(headers)

        for row in url_reader:
            writer.writerow([row[0], os.getenv('CONVERT_URL').format(
                urllib.parse.quote_plus(row[1])
            )])

            print(row[0] + ": " + gps_url_dict[row[0]] + "\n")
            

def get_all_gpx(driver):
    """
    Loop through each gps_vis url to download gpx files.
    """
    with open("gps_vis_urls.csv", newline="") as gps_vis_urls:
        url_reader = csv.reader(gps_vis_urls, delimiter=",")
        headers = next(url_reader)  # skip header

        for row in url_reader:
            try:
                submit_convert(driver, row)
            except Exception as e:
                print("An error occurred:", str(e))
                continue


def make_request(url, max_retries=5):
    """
    Make a request to the provided url.
    """
    retries = 0
    delay = 1
    while retries < max_retries:
        try:
            response = requests.get(url)
            if response.status_code == 200:
                return response
            elif response.status_code == 429:
                print(
                    "Received 429 Too Many Requests. Retrying in {} seconds...".format(
                        delay
                    )
                )
                time.sleep(delay)
                delay *= 2  # Exponential backoff
            else:
                print("Received status code:", response.status_code)
                return None
        except Exception as e:
            print("Exception:", e)
            return None
    print("Exceeded maximum number of retries.")
    return None


def submit_convert(driver, row):
    """
    Use final gps_vis url to download gpx file.
    """

    # go to gps_vis url
    driver.get(row[1])

    # make API key input visible
    focus_field = driver.find_element(By.ID, "remote_data_input")
    focus_field.send_keys(Keys.TAB)
    time.sleep(2)

    # fill in gmaps API key
    input_field = driver.find_element(By.ID, "input:google_api_key")
    input_field.clear()
    input_field.send_keys(os.getenv('GMAPS_API_KEY'))

    # submit form
    submit_button = driver.find_element(By.CLASS_NAME, "gpsv_submit")
    submit_button.click()

    # wait until next page is loaded
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.TAG_NAME, "iframe"))
    )

    # download gps file
    download_anchor = driver.find_element(By.PARTIAL_LINK_TEXT, "data.gpx")
    download_anchor.click()
    time.sleep(1)

    # count the number of files in dl dir
    files = os.listdir(dl_dir)
    num_files = len(files)

    # sort files by modification time to get most recent
    files.sort(
        key=lambda x: os.path.getmtime(os.path.join(dl_dir, x)), reverse=True
    )

    # move the most recent file to gpx dir
    if num_files > 0:
        most_recent_file = files[0]
        most_recent_file_path = os.path.join(dl_dir, most_recent_file)
        new_file_path = os.path.join(gpx_dir, "{}.gpx".format(row[0]))
        os.rename(most_recent_file_path, new_file_path)
    else:
        print("No files found in downloads directory.")
        
main()

