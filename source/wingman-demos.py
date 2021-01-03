import os
from types import CodeType
import requests
from bz2 import BZ2File
from argparse import ArgumentParser
from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, InvalidArgumentException, TimeoutException, WebDriverException
from selenium.webdriver.common.keys import Keys
import time
import datetime
from os.path import abspath, dirname

import subprocess
import sys, string, os

STEAM_PAGE = "https://steamcommunity.com"

target = dirname(abspath(__file__)).replace('\\','/') +"/"
if not os.path.exists(target + "temp"):
    os.makedirs(target + "temp")
source = target + "temp"
print(target)
def parseArgs():
    """
    Handle command line arguments
    """
    parser = ArgumentParser(
        description='Download CS:GO Wingman matches from your community profile page.')
    browserGroup = parser.add_mutually_exclusive_group()
    browserGroup.add_argument('-c', '--chrome', action='store_true',
                              help='use Google Chrome')
    parser.add_argument('-p', '--profile',
                        metavar='profiledir',
                        type=str,
                        help='custom path to browser profile directory')
    parser.add_argument('-k', '--keep-compressed', action='store_true',
                        help="keep the compressed demo files after download")
    parser.add_argument('-n', '--no-extraction', action='store_true',
                        help="don't extract the compressed demo files")
    parser.add_argument('-w', '--wait', action='store_true',
                        help="start the broswer and wait for login before continuing")
    parser.add_argument('-d', '--destination',
                        metavar='destination',
                        type=str,
                        help='where to store the demos')
    return parser.parse_args()


def getMissingArguments(args):
    """
    If required arguments are missing, prompt for them 
    """
    args.missingRequired = False
    # Missing browser
    if not args.chrome:
        args.missingRequired = True
        args.chrome = True
        # Ask whether the user is logged in

    if not args.destination:
        args.missingRequired = True
        customDestination = True
        args.destination = os.path.abspath(".")
        if customDestination:
            while(True):
                try:
                    path = source
                    if os.path.isdir(path):
                        args.destination = path
                        break
                    else:
                        print(
                            "Couldn't find that directory, please choose another or create it first!")
                except:
                    print(
                        "Couldn't find that directory, please choose another or create it first!")

    if args.missingRequired:
        print()
        print("Starting")
    return args


def getWebDriver(args):
    """
    Get the appopiate driver for chosen browser
    """
    driver = None
    if args.chrome:
        options = ChromeOptions()
        options.page_load_strategy = 'eager'
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        # Default profile directory
        userDataDir = os.getenv(
            'LOCALAPPDATA') + "\\Google\\Chrome\\User Data" if args.profile == None else args.profile
        options.add_argument("user-data-dir=" + userDataDir)
        driver = Chrome(options=options)
    return driver


def getBrowserName(args):
    if args.chrome:
        return "Chrome"
    return ""


def getUser(args, driver):
    """
    Get the logged in user
    """
    driver.get(STEAM_PAGE)
    try:  # Check for login button on homepage
        driver.find_element_by_link_text("login")
        if args.wait:  # Wait for login
            profileLinkElement = WebDriverWait(driver, 600).until(
                EC.presence_of_element_located((By.CLASS_NAME, "user_avatar")))
            username = profileLinkElement.get_attribute('href').split("/")[-2]
            return username
        return False
    except NoSuchElementException:  # Desired outcome, user is logged in
        profileLinkElement = driver.find_element_by_class_name(
            "user_avatar")  # top right profile pic
        username = profileLinkElement.get_attribute('href').split("/")[-2]
        return username
    except TimeoutException:
        print("Could not detect a user login within 10 minutes")
        return False


def getLinks(args):
    """
    Scan the steam community page for wingman demo links
    """
    links = []
    dates = []
    try:
        with getWebDriver(args) as driver:
            user = getUser(args, driver)
            if user:
                print(f"User {user} is logged in")
                # Get the demo download links
                if user.isdigit():
                    statlink = STEAM_PAGE + "/profiles/" + user + "/gcpd/730/?tab=matchhistorywingman"
                else:
                    statlink = STEAM_PAGE + "/id/" + user + "/gcpd/730/?tab=matchhistorywingman"
                driver.get(statlink)
                
                Found = False
                while not Found:
                    #GET DATES
                    MatchDate = driver.find_elements_by_xpath('//*[@id="personaldata_elements_container"]/table/tbody/tr/td[1]/table/tbody/tr[2]/td')
                    iter = 0
                    for element in MatchDate:                       
                        date = datetime.datetime.strptime(element.text, '%Y-%m-%d %H:%M:%S %Z')
                        dates.append(int(date.timestamp()))
                        if os.path.isfile(source + "/" + str(int(date.timestamp()))+".dem"):
                            Found = True
                            break
                        iter += 1
                    iter2 = 0
                    #GET LINKS
                    linkElements = driver.find_elements_by_xpath('//td[@class="csgo_scoreboard_cell_noborder"]/a')
                    for element in linkElements:
                        if iter == iter2:
                            break
                        href = element.get_attribute('href')
                        links.append(href)
                        iter2 += 1
                    #LOAD MORE
                    if Found == False:
                        try:
                            print("Load more matches")
                            loadMore = driver.find_element_by_xpath('//*[@id="mainContents"]/div[6]/a')
                            driver.execute_script("arguments[0].click();", loadMore)
                            time.sleep(2.5)
                        except:
                            print("ERROR: Failed to load more")
                            break
                print(f"Found {len(links)} demo" + ("s" if len(links) != 1 else ""))
            else:
                print("ERROR: No user is logged in")
            driver.quit()
    except InvalidArgumentException:
        print("ERROR: Browser is already running. Please close all instances of it before running this software.")
    except NoSuchElementException:
        print("ERROR: Could not find any recent matches")
    except WebDriverException:
        if args.chrome:
            print("ERROR: Could not find chromedriver.exe")
            print("Please download the correct version from https://chromedriver.chromium.org/ and put in the same directory as wingman-dl.exe")
    return links, dates


def downloadDemos(args, links, dates):
    """
    Download demos from the accumulated links
    """
    skippedDemos = 0
    downloadedDemos = 0
    erroredDemos = 0
    try:
        alreadyDownloaded = os.listdir(args.destination)
    except:
        print(
            f"ERROR: Failed to read destination path {args.destination}. Make sure you have the right permissions and that the directory exist.")
        return

    for x in range(len(links)):
        link = links[x]
        demoname = link.split("/")[-1]
        demoname = str(dates[x]) + ".dem.bz2"
        unzippedname = demoname[:-4]

        # Check if already downloaded
        if unzippedname in alreadyDownloaded or demoname in alreadyDownloaded:
            print(f"Skipping {demoname} (already downloaded)")
            skippedDemos += 1
            continue

        # Download
        print("Downloading", demoname)
        r = requests.get(link)
        if r.ok:
            # Write compressed demo to disk
            try:
                with open(args.destination + "/" + demoname, 'wb') as f:
                    f.write(r.content)
            except:
                print(f"ERROR: Could not write demo {demoname} to disk")
                erroredDemos += 1
                continue

            # Unzip the compressed demo
            if not args.no_extraction:
                try:
                    print("Unzipping", unzippedname.split("/")[-1])
                    with BZ2File(args.destination + "/" + demoname) as compressed:
                        data = compressed.read()
                        open(args.destination + "/" +
                             unzippedname, 'wb').write(data)
                except:
                    print(f"ERROR: Could not extract demo {demoname}")
                    erroredDemos += 1
                    continue

            # Delete compressed demo
            if not args.keep_compressed:
                try:
                    print("Removing", demoname)
                    os.remove(args.destination + "/" + demoname)

                except:
                    print(f"ERROR: Could not delete {demoname}")
                    erroredDemos += 1
                    continue
            downloadedDemos += 1
        else:
            print(
                f"ERROR: Could not download the demo. Maybe the steam download servers are down or link broken. Link: {link}")
    return skippedDemos, downloadedDemos, erroredDemos


def printResult(res):
    """
    Prints the number of downloaded, skipped and errored demos
    """
    skippedDemos, downloadedDemos, erroredDemos = res
    print()
    #print("RESULTS:")
    if(downloadedDemos != 0):
        print("Downloaded", downloadedDemos)
    if(skippedDemos != 0):
        print("Skipped", skippedDemos)
    if(erroredDemos != 0):
        print("Failed", erroredDemos)
    if(downloadedDemos+skippedDemos+erroredDemos == 0):
        print("Exiting...")
    print()
    #RENAME
    if(downloadedDemos != 0):
        exe = target + "Wingman.exe"
        subprocess.call([exe, source, target])
    
if __name__ == "__main__":
    args = parseArgs()
    args = getMissingArguments(args)
    FuncGetLinks = getLinks(args)
    links = FuncGetLinks[0]
    dates = FuncGetLinks[1]
    res = downloadDemos(args, links, dates)
    printResult(res)
