import aiofiles
import asyncio
import functools
import json
import os
import requests
import subprocess
import sys
import time

from metaplex import metadata
from solana.rpc.api import Client

#---------- REQUIRED ----------#
# Only set one of the following three values to True at a time
CREATE_JSON_ASSETS = False  # Creates json assets for each NFT using media files located in the assets folder
UPDATE_JSON_URIS = False  # Update the json URIs to point to new, "revealed" media files located on a file hosting site
# Metaboss must be installed to update JSON URIs (see readme on Github)
RENAME_MEDIA_FILES = False  # Can be used for when you have a large folder of files named something like TT_1.gif, TT_2.gif, TT_3.gif, etc.
NFT_NAME = ""  # Name of each NFT, it will automatically be appended with a "#NUMBER" like "NFT Name #1"
COLLECTION_NAME = ""  # Name of the collection
FAMILY_NAME = ""  # Name of the "parent" collection, or the group/company that is in charge of the collection
NFT_SUPPLY = 10  # Number of NFTs in the collection
DESCRIPTION = ""  # Description for the NFT
SELLER_FEE_BASIS_POINTS = 0  # The percentage of royalties to give to each creator but converted to "basis points",
# 0 would be no royalties received by the creator, 500 would be 5%, 1000 would be 10% and so forth
CREATOR_SHARES = [{"address": "","share": 100}]  # "Address" is public key of wallet(s) that will receive funds
# from minting and "share" is the % that each wallet gets - The total shares must equal 100. Can add more by appending
# to the list like the following: [{"address": "wallet-1","share": 50},{"address": "wallet-2","share": 50}]
BASE_IMAGE_URL = ""  # URL to the location where the images are stored (may be the same as BASE_VIDEO_URL)
IMAGE_FILE_EXTENSION = "png"  # File extension of the image files
USING_VIDEO_FILES = False  # Set to True if you are using video files, you will need to make sure you have both an
# image file and video file for each NFT. i.e. for NFT #1 you would need "0.png", "0.mp4" and "0.json" in your assets folder.
# The image file will be used as a backup for wallets that can't display videos.
BASE_VIDEO_URL = ""  # URL to the location where the videos are stored (may be the same as BASE_IMAGE_URL, leave blank if not using videos)
VIDEO_FILE_EXTENSION = ""  # File extension of the video files (leave blank if not using videos)

#---------- OPTIONAL ----------#
VERBOSE = True  # Set to True to see more detailed output and also log output to a file
SYMBOL = ""  # Symbol of the collection
ATTRIBUTES = [{"trait_type": "", "value": ""}]  # Leave blank if no attributes are used. Can add more by appending to
# the list like the following: [{"trait_type": "Trait 1", "value": "Red"},{"trait_type": "Trait 2", "value": "Blue"}]
ORIGINAL_FILENAME_PREFIX = ""  # Used for optional renaming of files. Expects a folder named "assets" with files that have names
# with a static prefix similar to "IMG_1.gif","IMG_1.mp4","IMG_2.gif", etc. and will rename them to "1.gif","1.mp4","2.gif", etc.
CANDY_MACHINE_ID = ""  # Necessary to retrieve the list of minted NFTs that will then be used to update the json URIs
BASE_JSON_URL = ""  # Used to update the json URIs for each NFT


cwd = os.path.dirname(os.path.realpath(__file__)) # This is the directory that contains a folder named "assets" (which holds all your json's and media files)
client = Client("http://api.mainnet-beta.solana.com") # You can enter your own RPC URL here if you want to use a different one


async def create_json_assets(i):
	if USING_VIDEO_FILES:
		data = {
			"name": f"{NFT_NAME} #{str(i + 1)}",
			"symbol": SYMBOL if SYMBOL != "" else None,
			"description": DESCRIPTION,
			"seller_fee_basis_points": SELLER_FEE_BASIS_POINTS,
			"image": f"{BASE_IMAGE_URL.rstrip('/')}/{str(i)}.{IMAGE_FILE_EXTENSION}?ext={IMAGE_FILE_EXTENSION}",
			"animation_url": f"{BASE_VIDEO_URL.rstrip('/')}/{str(i)}.{VIDEO_FILE_EXTENSION}?ext={VIDEO_FILE_EXTENSION}",
			"attributes": ATTRIBUTES if ATTRIBUTES[0]['trait_type'] != "" else None,
			"collection": {
				"name": COLLECTION_NAME,
				"family": FAMILY_NAME
			},
			"properties": {
				"files": [
					{
						"uri": f"{BASE_IMAGE_URL.rstrip('/')}/{str(i)}.{IMAGE_FILE_EXTENSION}?ext={IMAGE_FILE_EXTENSION}",
						"type": f"image/{IMAGE_FILE_EXTENSION}"
					},
					{
						"uri": f"{BASE_VIDEO_URL.rstrip('/')}/{str(i)}.{VIDEO_FILE_EXTENSION}?ext={VIDEO_FILE_EXTENSION}",
						"type": f"video/{VIDEO_FILE_EXTENSION}"
					}
				],
				"category": "video",
				"creators": CREATOR_SHARES
			}
		}
	else:
		data = {
			"name": f"{NFT_NAME} #{str(i + 1)}",
			"symbol": SYMBOL if SYMBOL != "" else None,
			"description": DESCRIPTION,
			"seller_fee_basis_points": SELLER_FEE_BASIS_POINTS,
			"image": f"{BASE_IMAGE_URL.rstrip('/')}/{str(i)}.{IMAGE_FILE_EXTENSION}?ext={IMAGE_FILE_EXTENSION}",
			"attributes": ATTRIBUTES if ATTRIBUTES[0]['trait_type'] != "" else None,
			"collection": {
				"name": COLLECTION_NAME,
				"family": FAMILY_NAME
			},
			"properties": {
				"files": [
					{
						"uri": f"{BASE_IMAGE_URL.rstrip('/')}/{str(i)}.{IMAGE_FILE_EXTENSION}?ext={IMAGE_FILE_EXTENSION}",
						"type": f"image/{IMAGE_FILE_EXTENSION}"
					}
				],
				"category": "image",
				"creators": CREATOR_SHARES
			}
		}
	data_to_write = json.dumps(data, indent=2)
	async with aiofiles.open(f"assets/{str(i)}.json", mode='w') as f:
		await f.write(str(data_to_write))
	await async_log(f"Saved json asset #{str(i)}")


async def rename_files(i):
	try: os.rename(f"assets/{ORIGINAL_FILENAME_PREFIX}{i}.gif", f"assets/{i}.gif")
	except: pass
	try: os.rename(f"assets/{ORIGINAL_FILENAME_PREFIX}{i}.png", f"assets/{i}.png")
	except: pass
	try: os.rename(f"assets/{ORIGINAL_FILENAME_PREFIX}{i}.jpeg", f"assets/{i}.jpeg")
	except: pass
	try: os.rename(f"assets/{ORIGINAL_FILENAME_PREFIX}{i}.jpg", f"assets/{i}.jpg")
	except: pass
	try: os.rename(f"assets/{ORIGINAL_FILENAME_PREFIX}{i}.mp4", f"assets/{i}.mp4")
	except: pass
	await async_log("Renamed asset group #" + str(i))


def get_minted_nfts():
	try:
		filename = f"{cwd}\\{CANDY_MACHINE_ID}_mint_accounts.json"
		if os.path.exists(filename):
			while True:
				log("Minted NFTs file already exists, would you like to generate a new one? (Y/n)")
				choice = input(">> ")
				if choice.lower() == "y" or choice.lower() == "yes":
					choice = True
					break
				elif choice.lower() == "n" or choice.lower() == "no":
					log("Using existing minted NFTs file.")
					choice = False
					break
				else:
					log("Invalid choice, please type either 'y' or 'n'.")
					continue
			if choice:
				log("Getting list of minted NFTs now, this may take a moment...")
				retries = 0
				while retries < 3:
					retries += 1
					res = subprocess.run(["cmd", "/c",f'cd {cwd} && metaboss snapshot mints -c {CANDY_MACHINE_ID} --v2 --timeout 240'],shell=True, capture_output=True)
					if res is None:
						log("Failed to get list of minted NFTs, retrying...")
						continue
					elif res.stderr is not None and len(res.stderr) > 0:
						log("Error getting list of minted NFTs: " + str(res.stderr.decode().replace('\n', ' ')))
						continue
					else:
						parsed_res = str(res.stdout.decode().replace('\n', ' '))
						if VERBOSE:
							log(f"Response from getting minted NFTs: \"{parsed_res}\"\n-----------------------------------")
						else:
							log("Got list of minted NFTs successfully!")
						break
		with open(filename, mode='r') as f:
			data = f.read()
		minted_nft_data = json.loads(data)
		return minted_nft_data
	except Exception as e:
		log("Error getting list of minted NFTs | Error:" + str(e))
		return None


def update_json_uris(minted_nft):
	retries = 0
	while retries < 3:
		retries += 1
		try:
			metadata = get_metadata(minted_nft)
			if metadata is None:
				return f"Failed to update URI for NFT: {minted_nft} | Error: Couldn't get metadata after retrying 3 times"
			nft_number = metadata["name"].split("#")[1].split(" ")[0]
			log(f"Updating URI for NFT #{str(nft_number)} | Mint address: {minted_nft}")
			if int(nft_number) != 0:
				nft_number = int(nft_number) - 1
			res = subprocess.run(["cmd", "/c",f'cd {str(cwd)} && metaboss update uri --account {minted_nft} --new-uri {BASE_JSON_URL.rstrip("/")}/{str(nft_number)}.json --timeout 240'], shell=True, capture_output=True)
			if res is None:
				log(f"Failed to update URI for NFT: {minted_nft}, trying again... Error: Couldn't get response from metaboss")
				continue
			elif res.stderr is not None and len(res.stderr) > 0:
				stderr = str(res.stderr.decode().replace('\n',' '))
				if stderr.find("unable to confirm transaction") != -1:
					log(f"Transaction failed, retrying for NFT #{str(int(nft_number) + 1)} | Mint address: {minted_nft}...")
					time.sleep(3)
					continue
				elif stderr.find("Node is behind") != -1:
					log(f"Node is behind, waiting 15s and retrying for NFT # {str(int(nft_number) + 1)} | Mint address: {minted_nft}...")
					time.sleep(15)
					continue
				else:
					log(f"Error updating URI for NFT #{str(int(nft_number) + 1)} | Mint address: {str(minted_nft)} | Error: {str(stderr)}")
					return f"Failed to update URI for NFT #{str(int(nft_number) + 1)} | Mint address: {minted_nft} | Error: {str(stderr)}"
			else:
				parsed_res = str(res.stdout.decode().replace('\n', ' '))
				log(f"Successfully updated URI for NFT #{str(int(nft_number) + 1)}")
				if VERBOSE:
					log(f"Response after updating URI: \"{parsed_res}\"\n-----------------------------------")
			return f"Successfully updated URI for NFT #{str(int(nft_number) + 1)} | Mint address: {minted_nft}"
		except Exception as e:
			log(f"Error updating URI for NFT: {minted_nft}: | Error: {str(e)}")
			return f"Failed to update URI for NFT: {minted_nft} | Error: {str(e)}"
	return f"Failed to update URI for NFT: {minted_nft} | Error: Failed after 3 retries"


def get_metadata(mint_id):
	retries = 0
	while retries < 3:
		retries += 1
		try:
			data = metadata.get_metadata(client, mint_id)['data']
			res = requests.get(data['uri'])
			return res.json()
		except Exception as e:
			log(f"Error getting metadata for NFT: {mint_id}, trying again now... Error: {str(e)}")
			continue
	log(f"Error getting metadata for NFT: {mint_id} after max retries, giving up!")
	return None


def log(message):
	print(message)
	if VERBOSE:
		with open(f"assets_helper_logs.log", mode='a') as f:
			f.write(f"{str(message)}\n")


async def async_log(message):
	print(message)
	if VERBOSE:
		async with aiofiles.open(f"assets_helper_logs.log", mode='a') as f:
			await f.write(f"{str(message)}\n")


async def main():
	tasks, results = [], []
	success, fail = 0, 0
	if UPDATE_JSON_URIS:
		minted_nfts = get_minted_nfts()
		if minted_nfts is None:
			await async_log("Error getting minted NFTs, exiting...")
			return
		for minted_nft in minted_nfts:
			res = update_json_uris(minted_nft)
			if res is not None and res.find("Success") != -1:
				success += 1
			else:
				fail += 1
			results.append(res)
		await async_log("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ RESULTS ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
		i = 0
		async with aiofiles.open(f"{CANDY_MACHINE_ID}_results_{str(time.strftime('%m%d%y%M%S'))}.log", mode='a') as f:
			for result in results:
				i += 1
				await async_log(f"#{str(i)}: {str(result)}")
				await f.write(f"{str(result)}\n")
		await async_log(f"Success: {str(success)} | Fail: {str(fail)}")
	else:
		for i in range(NFT_SUPPLY):
			if RENAME_MEDIA_FILES:
				tasks.append(asyncio.ensure_future(rename_files(i=i)))
			if CREATE_JSON_ASSETS:
				tasks.append(asyncio.ensure_future(create_json_assets(i=i)))
		await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == '__main__':
	start_time = time.perf_counter_ns() // 1_000_000
	asyncio.run(main())
	end_time = time.perf_counter_ns() // 1_000_000
	seconds = int(0.001 * (end_time - start_time))
	log(f"Exiting after {str(seconds)} seconds!")
