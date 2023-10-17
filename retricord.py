import requests
import os
import time
import random

request_cooldown_base = 100
request_cooldown_lower_rand = 10
request_cooldown_upper_rand = 50

debug_m = False

def query_string(queries):
	qs = "?"
	for i in queries:
		if queries[i] is not None:
			qs = qs + "%s=%s&" % (i, (str(queries[i]) if type(queries[i]) != bool else str(queries[i]).lower()))

	qs = qs.rstrip('&')
	
	if qs == "?":
		qs = "/"
	
	return qs

def main():

	# retrieve basic info...

	token = input("auth. ")
	channel_id = input("channel id. ")
	
	# retrieve channel name

	api_base_channel_url = "https://discord.com/api/v9/channels/%s" % channel_id

	headers = {
		'Authorization': token
	}

	response = requests.get(api_base_channel_url, headers=headers)
	
	if response.status_code != 200:
		print("invalid query.")
		print(response.content)
		return
	
	
	channel = response.json()
	if channel["type"] in (2, 4, 6, 13):
		print("channel is not text.")
		return
	
	if "name" not in channel:
		channel["name"] = None
	
	print("retrieved channel name: %s" % str(channel["name"]))
	
	# generating document
	
	print("generating document..")
	dirname = str(channel["name"]) + '-' + str(time.time())
	forbidden_characters = ('\\', '/', ':', '*', '?', '"', '<', '>', '|')
	for i in forbidden_characters:
		dirname = dirname.replace(i, '')
		
	os.mkdir(dirname)
	os.mkdir(dirname + os.path.sep + "assets")
	
	template_file = open("template.html", "r", encoding="utf-8")
	destination_file = open(dirname + os.path.sep + "index.html", "w", encoding="utf-8")
	vars_file = open(dirname + os.path.sep + "vars.js", "w", encoding="utf-8")
	
	destination_file.write(template_file.read())
	
	template_file.close()
	destination_file.close()
	
	# logic
	
	tbw_string = """channel_name = "%s";\n""" % str(channel["name"]) + \
		"""vars_dict = {\n"""
		
	vars_file.write(tbw_string)
	current_file_pos = vars_file.tell()
	vars_file.write("};")
	vars_file.flush()
	
	users = []
	last_message_id = None
	
	cnt = 0
	
	while True:
		response = requests.get(api_base_channel_url + "/messages" + query_string({"before": last_message_id, "limit": 100}), headers=headers)
		if response.status_code == 429:
			retry_after = response.json()["retry_after"]
			print("i am being rate limited for %s seconds." % str(retry_after))
			time.sleep(retry_after)
			continue
		
		if response.status_code != 200:
			print("non-ok status code, and not rate limited.")
			print("more information - status code: %s" % str(response.status_code))
			print(response.text)
			input("press any key to resume")
			continue

		if debug_m:
			print(response.text)
			
		c_response = response.json()
		print("retrieved next batch of %d messages. processing.." % len(c_response))
		
		if len(c_response) == 0:
			print("indexed the entire channel. exiting..")
			break
		
		html_lines = []
		last_message_author = None
		
		for i in c_response:
			author = i["author"]
			if author["id"] not in users:
			
				# new user
				# add new user to vars file
				
				vars_file.seek(current_file_pos)
				vars_file.truncate()
				vars_file.write(""""user-%s": "%s",\n""" % (author["id"], "%s#%s" % (author["username"], author["discriminator"])))
				current_file_pos = vars_file.tell()
				vars_file.write("};")
				vars_file.flush()
				
				# grab profile picture and save it under assets
				
				if author["avatar"] is None:
					pfp_url = "https://cdn.discordapp.com/embed/avatars/%d.png" % (int(author["discriminator"]) % 5)
				else:
					pfp_url = "https://cdn.discordapp.com/avatars/%s/%s.png" % (author["id"], author["avatar"])
				pfp_response = requests.get(pfp_url)
				with open("%s%sassets%s%s.png" % (dirname, os.path.sep, os.path.sep, author["id"]), "wb") as pfp_file:
					pfp_file.write(pfp_response.content)
					
				# remember
				users.append(author["id"])
				
			
			timestamp_text = i["timestamp"]
			if i["edited_timestamp"]:
				timestamp_text = timestamp_text + " (edited %s)" % i["edited_timestamp"]
			
			# if author CHANGES, close previous message	
			
			if last_message_author and author["id"] != last_message_author:
				html_lines.append("""\t\t</div>""")
				html_lines.append("""\t</div>""")
				html_lines.append("""</div>""")
				html_lines.append("""""")
				
			# if author CHANGES or is the first, open a new message and add a pfp and name
				
			if author["id"] != last_message_author:
				html_lines.append("""<div class="message">""")
				html_lines.append("""\t<div style="float: left;">""")
				html_lines.append("""\t\t<img class="pfp" src="assets/%s.png">""" % author["id"])
				html_lines.append("""\t</div>""")
				html_lines.append("""\t<div style="float: left;">""")
				html_lines.append("""\t\t<h3><user-%s></user-%s></h3>""" % (author["id"], author["id"]))
				html_lines.append("""\t\t<div style="display: flex; flex-direction: column-reverse;">""")
			
			# write message regardless, with attachments
			# TODO: change behaviour when reversed

			for j in range(len(i["attachments"]) - 1, -1, -1):
				attachment = i["attachments"][j]
				os.mkdir("%s%sassets%s%s" % (dirname, os.path.sep, os.path.sep, attachment["id"]))
				attachment_response = requests.get(attachment["url"])
				with open("%s%sassets%s%s%s%s" % (dirname, os.path.sep, os.path.sep, attachment["id"], os.path.sep, attachment["filename"]), "wb") as attachment_file:
					attachment_file.write(attachment_response.content)
					
				attachment_file.close()
				html_lines.append("""<p><a href="assets/%s/%s" target="_blank">Attachment</a></p>""" % (attachment["id"], attachment["filename"]))
			
			html_lines.append("""\t\t\t<p>%s</p>""" % i["content"])
			html_lines.append("""\t\t\t<p class="dt">%s</p>""" % timestamp_text)
			
			last_message_author = author["id"]
			last_message_id = i["id"]
		
		# close previous message if not empty (shouldn't be anyway..)
		
		if len(html_lines) > 0:
			html_lines.append("""\t\t</div>""")
			html_lines.append("""\t</div>""")
			html_lines.append("""</div>""")
			html_lines.append("""""")
		
		html_string = ""
		for i in html_lines:
			html_string = html_string + '\t' * 6 + i + '\n'
			
		html_string = html_string[:-1]
		html_string = html_string + "<!-- here! -->"
		
		# modify destination file
		
		destination_file = open(dirname + os.path.sep + "index.html", "r", encoding="utf-8")
		destination_file_text = destination_file.read()
		destination_file.close()
		destination_file_text = destination_file_text.replace("<!-- here! -->", html_string)
		destination_file = open(dirname + os.path.sep + "index.html", "w", encoding="utf-8")
		destination_file.write(destination_file_text)
		destination_file.close()
		
		cnt += 1
		print("batch #%d completed." % cnt)
		
		to_wait = request_cooldown_base + random.randint(request_cooldown_lower_rand, request_cooldown_upper_rand)
		
		print("waiting %d ms" % to_wait)
		
		time.sleep(to_wait / 1000)
	
if __name__ == "__main__":
	main()