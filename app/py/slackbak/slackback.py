__author__ = 'chitrabhanu'


import os
from slackclient import SlackClient
import requests
import sys
import datetime
import time
import json
from json2html import json2html

# This value is used as a delay between successive page requests to avoid getting rate limited by Slack
SECONDS_BETWEEN_SUCCESSIVE_PAGE_REQUESTS = 2

RUNTIME_ERROR_PREFIX = "RUNTIME ERROR: "

class RuntimeError(Exception):

    def __init__(self, msg):
        self.msg = RUNTIME_ERROR_PREFIX + msg

class Iima79SlackBack:

    def __init__(self, slack_client, slack_token):
        self.slack_client = slack_client
        self.slack_token=slack_token
        self.epoch = datetime.datetime(1970,1,1)
        self.run_datetime = datetime.datetime.today().strftime("%Y-%m-%d-%H-%M")
        self.run_label = "cull_de_slack-"+ self.run_datetime
        self.channels = {}
        self.channels_html = ""
        self.channel_id_by_name = {}
        self.groups = {}
        self.groups_html = ""
        self.users = {}
        self.users_html = ""
        self.files = {}
        self.files_html = ""
        self.current_channel_messages = []
        self.channel_yr_mth_lists = {}
        self.output_dir = os.path.join(".", self.run_label)
        self.merge_input_dirs = None
        self.channels_json = "channels.json"
        self.groups_json = "groups.json"
        self.users_json = "users.json"
        self.files_json = "files.json"
        self.messages_json_suffix = "_messages.json"
        self.html_prefix = "file:///nobackup/websaves/"
        self.valid_ops = ["CLEAR", "GET", "SAVE","MERGE","RENDER"]
        self.html_prolog = "<!DOCTYPE html>\n<html>\n<head>\n<title></title>\n</head>\n<body>"
        self.html_epilog = "</body>\n</html>"
        self.link_indicator = "___"

    def set_run_label(self, run_label):
        self.run_label = run_label
        
    def get_run_label(self):
        return self.run_label
        
    def set_output_dir(self, output_dir):
        self.output_dir = output_dir
        
    def get_output_dir(self):
        return self.output_dir
        
    def set_merge_input_dirs(self, merge_input_dirs):
        self.merge_input_dirs = merge_input_dirs
        
    def get_merge_input_dirs(self):
        return self.merge_input_dirs
        
    def set_channels_json(self, channels_json):
        self.channels_json = channels_json
        
    def get_channels_json(self):
        return self.channels_json
        
    def set_channels_html(self, channels_html):
        self.channels_html = channels_html
        
    def get_channels_html(self):
        return self.channels_html
        
    def set_groups_json(self, groups_json):
        self.groups_json = groups_json
        
    def get_groups_json(self):
        return self.groups_json
        
    def set_groups_html(self, groups_html):
        self.groups_html = groups_html
        
    def get_groups_html(self):
        return self.groups_html
        
    def set_users_json(self, users_json):
        self.users_json = users_json
        
    def get_users_json(self):
        return self.users_json
        
    def set_users_html(self, users_html):
        self.users_html = users_html
        
    def get_users_html(self):
        return self.users_html
        
    def set_files_json(self, files_json):
        self.files_json = files_json
        
    def get_files_json(self):
        return self.files_json
        
    def set_files_html(self, files_html):
        self.files_html = files_html
        
    def get_files_html(self):
        return self.files_html
        
    def set_messages_json_suffix(self, messages_json_suffix):
        self.messages_json_suffix = messages_json_suffix
        
    def get_messages_json_suffix(self):
        return self.messages_json_suffix
        
    def set_html_prefix(self, html_prefix):
        self.html_prefix = html_prefix
        
    def get_html_prefix(self):
        return self.html_prefix
        
    def process_channels(self, ops ):
        for op in ops:
            if op not in self.valid_ops:
                raise RuntimeError(__name__+"::"+" invalid op " +  str(op) + " valid ops " +  str(self.valid_ops))
        ops = set(ops)
        if "CLEAR" in ops:
            self.clear_channels()
            ops.remove("CLEAR")
        if "GET" in ops:
            self.get_channels() # We do not load messages to save memory
            ops.remove("GET")
        if "SAVE" in ops:
            self.save_channels()
            ops.remove("SAVE")
        if "RENDER" in ops:
            self.render_channels()
            ops.remove("RENDER")
        if "MERGE" in ops:
            self.merge_channels()
            ops.remove("MERGE")

    def clear_channels(self):
        self.current_channel_messages = {}
        self.channels={}

    def get_channels(self):
        limit = 20
        cursor = None
        while cursor is None or cursor != '':
            resp = self.slack_client.api_call("channels.list", limit=limit, cursor=cursor)
            if resp.get('ok'):
                for channel in resp['channels']:
                    self.get_full_channel(channel['id'])
                cursor = resp['response_metadata']['next_cursor']
            else:
                raise RuntimeError(__name__+"::"+str(resp))
            time.sleep(SECONDS_BETWEEN_SUCCESSIVE_PAGE_REQUESTS)

    def get_full_channel(self, channel_id):
        resp = self.slack_client.api_call("channels.info", channel=channel_id)
        if resp.get('ok'):
            self.channels[resp['channel']['id']] = resp['channel']
            self.channel_id_by_name[resp['channel']['name']] = resp['channel']['id']
        else:
            raise RuntimeError(__name__+"::"+str(resp))

    def save_channels(self):
        summaries_dir = self.get_summaries_dir()
        output_file_name = os.path.join(summaries_dir, self.channels_json)
        with self.create_file(output_file_name, "w") as save_fd:
            json.dump(self.channels, save_fd)
        for channel_id in self.channels:
            self.save_messages(channel_id)
        
    def render_channels(self):
        output_json = {"channels" : []}
        for channel_id in self.channels:
            info = {}
            info ["Name"] = self.channels[channel_id]["name"]
            info ["Topic"] = self.channels[channel_id]["topic"]["value"]
            info ["Purpose"] = self.channels[channel_id] ["purpose"]["value"]
            list_index = 0
            later_messages_json_path = None
            for year_mth in self.channel_yr_mth_lists[channel_id]:
                messages_json_path = self.get_messages_json_path(channel_id, year_mth)
                if list_index == len(self.channel_yr_mth_lists[channel_id]) - 1:
                    earlier_messages_json_path = None
                else:
                    earlier_messages_year_mth = self.channel_yr_mth_lists[channel_id][list_index + 1]
                    earlier_messages_json_path =\
                        self.get_messages_json_path(channel_id, earlier_messages_year_mth)
                result = self.create_rendered_messages(self.channels[channel_id]["name"], year_mth,
                                                       messages_json_path, later_messages_json_path,\
                                                       earlier_messages_json_path)
                if result:
                    link = self.get_href(messages_json_path.replace(".json", ".html"), year_mth)
                    if "Latest Messages" not in info:
                        info ["Latest Messages"] = link
                    info ["Earliest Messages"] = link
                later_messages_json_path = self.get_messages_json_path(channel_id, year_mth)
                list_index += 1
            output_json ["channels"].append(info)
        if output_json["channels"] != []:
            self.channels_html = json2html.convert(json = output_json)
        else:
            self.channels_html = ""

    def merge_channels(self):
        pass

    def clear_messages(self, channel_id):
        if channel_id in self.current_channel_messages:
            del self.current_channel_messages[channel_id]

    def save_messages(self, channel_id):
        latest = None
        has_more = True
        self.current_channel_messages = []
        year_mth = ""
        while has_more:
            resp = self.slack_client.api_call("channels.history", channel=channel_id, latest=latest)
            if resp.get('ok'):
                has_more = resp["has_more"]
                for message in resp['messages']:
                    new_year_mth=self.get_yr_mth_for_ts(message["ts"])
                    if new_year_mth != year_mth:
                        if year_mth != "":
                            output_file_name = os.path.join(self.output_dir,\
                                                            self.get_messages_json_path(channel_id, year_mth))
                            with self.create_file(output_file_name, "w") as save_fd:
                                json.dump(self.current_channel_messages, save_fd)
                            if channel_id not in self.channel_yr_mth_lists:
                                self.channel_yr_mth_lists[channel_id] = []
                            self.channel_yr_mth_lists[channel_id].append(year_mth)
                        year_mth = new_year_mth
                        self.current_channel_messages = []
                    self.current_channel_messages.append(message)
                    latest = message["ts"]
            else:
                raise RuntimeError(__name__+"::"+str(resp))
            time.sleep(SECONDS_BETWEEN_SUCCESSIVE_PAGE_REQUESTS)
        if year_mth != "":
            output_file_name = os.path.join(self.output_dir, self.get_messages_json_path(channel_id, year_mth))
            with self.create_file(output_file_name, "w") as save_fd:
                json.dump(self.current_channel_messages, save_fd)
            if channel_id not in self.channel_yr_mth_lists:
                self.channel_yr_mth_lists[channel_id] = []
            self.channel_yr_mth_lists[channel_id].append(year_mth)

    def get_messages_json_path(self, channel_id, year_mth):
        output_path = os.path.join(self.output_dir, year_mth)
        self.create_dir(output_path)
        output_file_name = self.channels[channel_id]["name"] + self.messages_json_suffix
        return os.path.join(year_mth, output_file_name)

    def create_rendered_messages(self, channel_name, year_mth, messages_json_path, later_messages_json_path,\
                                 earlier_messages_json_path):
        with open(os.path.join(self.output_dir, messages_json_path)) as fd:
            input_json = json.load(fd)
        output_json = {}
        if later_messages_json_path is not None:
            link = later_messages_json_path.replace(".json", ".html")
            text = link.replace(".html", "")
            output_json["Later messages"] = self.get_href(link, text)
        if earlier_messages_json_path is not None:
            link = earlier_messages_json_path.replace(".json", ".html")
            text = link.replace(".html", "")
            output_json["Earlier messages"] = self.get_href(link, text)
        output_json["messages"] = []
        for message in input_json:
            output_message_object = {}
            if "subtype" not in message:
                output_message_object["From"] = self.users[message["user"]]["name"]
                output_message_object["Time"] = self.get_ca_time_str_for_ts(message["ts"]) + "(ts = " + message["ts"] + ")"
                output_message_object["Text"] = message ["text"]
            elif message["subtype"] ==  "file_share" or message["subtype"] == "file_mention":
                output_message_object["From"] = self.users[message["user"]]["name"]
                output_message_object["Time"] = self.get_ca_time_str_for_ts(message["ts"]) + "(ts = " + message["ts"] + ")"
                output_message_object["Text"] = message["subtype"]
                output_message_object["File"] = self.get_file_link_for_file(message["file"])
            if output_message_object != {}:
                output_json["messages"].append(output_message_object)
        messages_html_path = messages_json_path.replace(".json", ".html")
        if output_json["messages"] != []:
            messages_html = "<h3>" + channel_name + " Messages " + year_mth + "</h3>"
            messages_html += "<br />" + self.get_href(messages_json_path, "Click here for more Messages info") + ". "
            messages_html += "(To locate a particular message use your browser to search for its ts (in parentheses after the time) from the table below)"
            messages_html = messages_html + json2html.convert(json = output_json)
            self.create_html_page(os.path.join(self.output_dir, messages_html_path), messages_html)
            return True
        else:
            return False

    def merge_messages(self):
        pass

    def post_message_to_channel(self, channel_id, text):
        resp = self.slack_client.api_call("chat.postMessage", channel=channel_id, text=text)
        if resp.get('ok'):
            pass
        else:
            raise RuntimeError(__name__+"::"+str(resp))

    def delete_messages(self, year_mth):
        summaries_dir = self.get_summaries_dir()
        channels_load_file_name = os.path.join(summaries_dir, self.channels_json)
        with open(channels_load_file_name) as load_fd:
            channels = json.load(load_fd)
        total = 0
        for channel_id in channels:
            load_dir = os.path.join(self.output_dir, year_mth)
            messages_file_name = channels[channel_id]["name"] + self.messages_json_suffix
            messages_load_file_name = os.path.join(load_dir, messages_file_name)
            if os.path.isfile(messages_load_file_name):
                with open(messages_load_file_name) as load_fd:
                    messages = json.load(load_fd)
                    count = 0
                    for message in messages:
                        resp = self.slack_client.api_call("chat.delete", channel=channel_id, ts=message["ts"])
                        if resp.get('ok'):
                            print(message["ts"])
                        else:
                            print(message["ts"] + " " + str(resp))
                            #Raise RuntimeError(__name__+"::"+str(resp))
                        count += 1
                        time.sleep(SECONDS_BETWEEN_SUCCESSIVE_PAGE_REQUESTS)
                    print("CHANNEL: " + channels[channel_id]["name"] + ": " + str(count) + " messages deleted from " + year_mth)
                    total += count
        print("TOTAL " +  str(total) +  " messages deleted from " +  year_mth)

    def delete_files(self, year_mth):
        summaries_dir = self.get_summaries_dir()
        files_load_file_name = os.path.join(summaries_dir, self.files_json)
        with open(files_load_file_name) as load_fd:
            files = json.load(load_fd)
        count = 0
        for file_id in files:
            file_year_mth = self.get_yr_mth_for_ts(files[file_id]["created"])
            if file_year_mth != year_mth:
                continue
            resp = self.slack_client.api_call("files.delete", file=file_id)
            if resp.get('ok'):
                pass
            else:
                raise RuntimeError(__name__+"::"+str(resp))
            count += 1
            time.sleep(SECONDS_BETWEEN_SUCCESSIVE_PAGE_REQUESTS)
        print(str(count) +  " files deleted from " +  year_mth)

    def process_groups(self, ops, ):
        for op in ops:
            if op not in self.valid_ops:
                raise RuntimeError(__name__+"::"+" invalid op " +  str(op) + " valid ops " +  str(self.valid_ops))
        ops = set(ops)
        if "CLEAR" in ops:
            self.clear_groups()
            ops.remove("CLEAR")
        if "GET" in ops:
            self.get_groups()
            ops.remove("GET")
        if "SAVE" in ops:
            self.save_groups()
            ops.remove("SAVE")
        if "RENDER" in ops:
            self.render_groups()
            ops.remove("RENDER")
        if "MERGE" in ops:
            self.merge_groups()
            ops.remove("MERGE")

    def clear_groups(self):
        self.groups={}

    def get_groups(self):
        resp = self.slack_client.api_call("groups.list")
        if resp.get('ok'):
            for group in resp['groups']:
                self.groups[group['id']] = group
        else:
            raise RuntimeError(__name__+"::"+str(resp))
        
    def save_groups(self):
        summaries_dir = self.get_summaries_dir()
        output_file_name = os.path.join(summaries_dir, self.groups_json)
        with self.create_file(output_file_name, "w") as save_fd:
            json.dump(self.groups, save_fd)

    def render_groups(self):
        output_json = {"groups" : []}
        for group_id in self.groups:
            info = {}
            info ["Name"] = self.groups[group_id]["name"]
            info ["Topic"] = self.groups[group_id]["topic"]["value"]
            info ["Purpose"] = self.groups[group_id]["purpose"]["value"]
            output_json ["groups"].append(info)
        if output_json["groups"] != []:
            self.groups_html = json2html.convert(json = output_json)
        else:
            self.groups_html = ""

    def merge_groups(self):
        pass

    def process_users(self, ops, ):
        for op in ops:
            if op not in self.valid_ops:
                raise RuntimeError(__name__+"::"+" invalid op " +  str(op) + " valid ops " +  str(self.valid_ops))
        ops = set(ops)
        if "CLEAR" in ops:
            self.clear_users()
            ops.remove("CLEAR")
        if "GET" in ops:
            self.get_users()
            ops.remove("GET")
        if "SAVE" in ops:
            self.save_users_and_images()
            ops.remove("SAVE")
        if "RENDER" in ops:
            self.render_users()
            ops.remove("RENDER")
        if "MERGE" in ops:
            self.merge_users()
            ops.remove("MERGE")

    def clear_users(self):
        self.users={}

    def get_users(self):
        limit = 200
        cursor = None
        while cursor is None or cursor != '':
            resp = self.slack_client.api_call("users.list", limit=limit, cursor=cursor)
            if resp.get('ok'):
                for user in resp['members']:
                    self.users[user['id']] = user
                cursor = resp['response_metadata']['next_cursor']
            else:
                raise RuntimeError(__name__+"::"+str(resp))
            time.sleep(SECONDS_BETWEEN_SUCCESSIVE_PAGE_REQUESTS)

    def save_users_and_images(self):
        summaries_dir = self.get_summaries_dir()
        output_file_name = os.path.join(summaries_dir, self.users_json)
        with self.create_file(output_file_name, "w") as save_fd:
            json.dump(self.users, save_fd)
        # Uncomment this code after doing the self-service version of this program because
        # Slack provides image dir access only to specific users
        #for user_id in self.users:
        #    for key in self.users[user_id]["profile"]:
        #        if isinstance(key, unicode) and key.startswith("image"):
        #            url = self.users[user_id]["profile"][key]
        #            images_dir = os.path.join(summaries_dir, (self.users[user_id]["name"] + "_" + "images"))
        #            self.create_dir(images_dir)
        #            file_name = os.path.split(url)[-1:][0]
        #            self.save_file(file_name, url, images_dir)
        #            os.rename(os.path.join(images_dir, file_name), os.path.join(images_dir, (key + ".jpg")))
        
    def render_users(self):
        output_json = {"users" : []}
        for user_id in self.users:
            info = {}
            info ["Name"] = self.users[user_id]["name"]
            if "real_name" in self.users[user_id]["profile"]:
                info ["Real Name"] = self.users[user_id]["profile"]["real_name"]
            else:
                info["Real Name"] = "?"
            if "email" in self.users[user_id]["profile"]:
                info ["Email"] = self.users[user_id]["profile"]["email"]
            else:
                info["Email"] = "?"
            # Uncomment this code after doing the self-service version of this program because
            # Slack provides image dir access only to specific users
            #images_dir = os.path.join(summaries_dir, (user_id + "_" + "images"))
            #if os.path.isdir(images_dir):
            #    files = os.listdir(images_dir)
            #    if files != []:
            #        for file in files:
            #            file_path = os.path.join(images_dir, file)
            #            info["file"] = self.get_href(file_path, file)
            output_json ["users"].append(info)
        if output_json["users"] != []:
            self.users_html = json2html.convert(json = output_json)
        else:
            self.users_html = ""

    def merge_users(self):
        pass

    def process_files(self, ops, output_dir=None):
        for op in ops:
            if op not in self.valid_ops:
                raise RuntimeError(__name__+"::"+" invalid op " +  str(op) + " valid ops " +  str(self.valid_ops))
        ops = set(ops)
        if "CLEAR" in ops:
            self.clear_files()
            ops.remove("CLEAR")
        if "GET" in ops:
            self.get_files()
            ops.remove("GET")
        if "SAVE" in ops:
            self.save_files()
            ops.remove("SAVE")
        if "RENDER" in ops:
            self.render_files()
            ops.remove("RENDER")
        if "MERGE" in ops:
            self.merge_files()
            ops.remove("MERGE")

    def clear_files(self):
        self.files={}

    def save_file_and_thumbs(self, file_id):
        file_name = self.files[file_id]["name"]
        url = self.files[file_id]["url_private_download"]
        output_dir = self.get_output_dir_for_ts(self.files[file_id]["created"])
        self.save_file(file_name, url, output_dir)
        for key in self.files[file_id]:
            # The third term below reflects the fact that some self.files[file_id]["thumb_xxx"]
            # entries are ints (eg 1024) and not unicode strings
            if isinstance(key, unicode) and\
                    key.startswith("thumb") and \
                    isinstance(self.files[file_id][key], unicode) and\
                    self.files[file_id][key].startswith("http"):
                url = self.files[file_id][key]
                images_dir = os.path.join(output_dir, (file_id + "_" + "images"))
                self.create_dir(images_dir)
                file_name = os.path.split(url)[-1:][0]
                self.save_file(file_name, url, images_dir)

    def save_file(self, file_name, url, output_dir):
        resp=requests.get(url, headers={'Authorization': 'Bearer %s' % self.slack_token}, stream=True)
        with self.create_file(os.path.join(output_dir, file_name), 'wb') as fd:
            for chunk in resp.iter_content(chunk_size=1024):
                fd.write(chunk)

    def get_files(self):
        page = 1
        pages = 1 # Starting default, actual value will be fetched
        while (page - 1) < pages:
            resp = self.slack_client.api_call("files.list", page = page)
            if resp.get('ok'):
                for file in resp['files']:
                    self.files[file['id']] = file
                pages = resp['paging']['pages']
            else:
                raise RuntimeError(__name__+"::"+str(resp))
            page += 1
            time.sleep(SECONDS_BETWEEN_SUCCESSIVE_PAGE_REQUESTS)

    def save_files(self):
        summaries_dir = self.get_summaries_dir()
        output_file_name = os.path.join(summaries_dir, self.files_json)
        with self.create_file(output_file_name, "w") as save_fd:
            json.dump(self.files, save_fd)
        for file_id in self.files:
            self.save_file_and_thumbs(file_id)

    def render_files(self):
        output_json = {"files" : []}
        for file_id in self.files:
            info = {}
            info ["Title"] = self.files[file_id]["title"]
            info ["Link"] = self.get_file_link_for_file(self.files[file_id])
            output_json ["files"].append(info)
        if output_json["files"] != []:
            self.files_html = json2html.convert(json = output_json)
        else:
            self.files_html = ""

    def merge_files(self):
        pass

    def create_index_file(self):
        html = ""
        html+= "<h2>" + "CULL-DE-SLACK generated output: " + self.run_label + ": " + self.run_datetime + "</h2>"
        html += "<ol>"
        html += "<li>CULL-DE-SLACK is an acronym for C-B U-ncle\'s L-ovely L-ittle D-oorway E-ntering S-lack!!</li>"
        html += "<li>It deletes files and messages from our Slack group and generates them here to keep us within our Free Tier limits</li>"
        html += "<li>This website will be replaced by a snazzier, jazzier version so do not fret if you find it somewhat stilted/mechanized! This is temporary</li>"
        html += "<li>Should you hit problems, email CBD at: <a href=\"mailto:uncostservices@uncostservices.com\">CBD</a></li>"
        html += "</ol>"
        html += "<a name=\"top\"></a>\n"
        if self.channels_html != "":
           html += "<h3><a href=\"#channels\">Channels and Messages </a></h3>\n"
        if self.users_html != "":
           html += "<h3><a href=\"#users\">Users  </a></h3>\n"
        if self.files_html != "":
           html += "<h3><a href=\"#files\">Files  </a></h3\n>"
        html += "<h3><a href=\"#fordevelopers\">For Developers (placeholder till we can get our public CULL-DE-SLACK website up)</a></h3\n>"
        if self.channels_html != "":
            html += "<a name=\"channels\"></a>\n"
            html += "<h4><a href=\"#top\">Back to top</a></h4\n>"
            html += "<h3>CHANNELS and MESSAGES</h3>\n"
            channels_json_path = os.path.join(self.get_summaries_dir(), self.get_channels_json())
            html += "<br /><a href = \"" + channels_json_path + "\">Click here for (excruciatingly detailed!) Channels info</a>.  (To locate a particular channel use your browser to search for its name from the table below)"
            html += self.channels_html
        if self.users_html != "":
            html += "<a name=\"users\"></a>\n"
            html += "<h4><a href=\"#top\">Back to top</a></h4\n>"
            html += "<h3>USERS</h3>\n"
            users_json_path = os.path.join(self.get_summaries_dir(), self.get_users_json())
            html += "<br /><a href = \"" + users_json_path + "\">Click here for (excruciatingly detailed!) Users info</a>.  (To locate a particular channel use your browser to search for the (user) name from the table below)"
            html += self.users_html
        if self.files_html != "":
            html += "<a name=\"files\"></a>\n"
            html += "<h4><a href=\"#top\">Back to top</a></h4\n>"
            html += "<h3>FILES</h3>\n"
            files_json_path = os.path.join(self.get_summaries_dir(), self.get_files_json())
            html += "<br /><a href = \"" + files_json_path + "\">Click here for (excruciatingly detailed!) Files info</a>.  (To locate a particular file use your browser to search for its name from the table below)"
            html += self.files_html
        html += "<a name=\"fordevelopers\"></a>\n"
        html += "<h3>FOR DEVELOPERS</h3>\n"
        html += "<h5>If you are a developer interested in the code that generated this report:</h5>\n"
        html += "<ul>"
        html += "<li>It will be open sourced and will ultimately be available at <a href=\"https://github.com/unchaoss\">The Unchaoss repository at Github</a></li>"
        html += "<li>It is in pure Python and uses packages only from PyPi</li>"
        html += "<li>The intent is to grow it into a full service Slack interface for developers (along the lines of - but more full-featured than - <a href=\"https://pypi.python.org/pypi/slacker/\">Slacker</a>)</li>"
        html += "<li>Developer Email: <a href=\"mailto:uncostservices@uncostservices.com\">Uncost Services</a></li>"
        html += "</ul>"
        html += "<p>Note that for a full solution to Slack backup you will need to allow individual users to run this code since even the admin cannot access private messages for deletion. (Depending on your solution) this may require creation of a Web portal, and/or the use of non-Pythonic environments.</p>"
        self.create_html_page(os.path.join(self.get_summaries_dir(), "index.html"), html)

    def get_file_link_for_file(self, file):
        file_name = file["name"]
        year_mth = self.get_yr_mth_for_ts(file["created"])
        file_path = os.path.join(year_mth, file_name)
        return self.get_href(file_path, file_name)

    def get_href(self, target, text = ""):
        return self.link_indicator + self.html_prefix + target + self.link_indicator + text + self.link_indicator

    def get_ca_time_str_for_ts(self, gmt_ts):
        microseconds_since_epoch = float(gmt_ts) * 1000000
        gmt_offset_microseconds = 8 * 3600 * 1000000
        if self.is_dst(gmt_ts):
            gmt_offset_microseconds -= (3600 * 1000000)
        microseconds_since_epoch -= gmt_offset_microseconds
        return str(self.epoch + datetime.timedelta(microseconds=microseconds_since_epoch))

    def is_dst(self, gmt_ts):
        return True # For now. TODO

    def get_yr_mth_for_ts(self, gmt_ts):
        return self.get_ca_time_str_for_ts(gmt_ts)[0:7]

    def get_output_dir_for_ts(self, gmt_ts):
        year_mth = self.get_yr_mth_for_ts(gmt_ts)
        output_dir = os.path.join(self.output_dir, year_mth)
        self.create_dir(output_dir)
        return output_dir

    def get_summaries_dir(self):
        output_dir = os.path.join(self.output_dir, ("slackback" + self.run_label))
        self.create_dir(output_dir)
        return output_dir

    def create_file(self, file_name, mode):
        if os.path.isfile(file_name):
            try:
                os.rename(file_name, (file_name + "." + self.run_datetime))
            except IOError as err:
                raise RuntimeError(str(err) + " renaming file " +  file_name +\
                                   " to " + (file_name + "." + self.run_datetime))
        try:
            fd = open(file_name, mode)
            return fd
        except IOError as err:
            raise RuntimeError(str(err) + " creating " +  file_name)

    def create_html_page(self, file_name, html_text):
        html_after_handling_link_indicators = ""
        # Look for leading (link) indicator
        index = html_text.find(self.link_indicator)
        while index != -1:
            html_after_handling_link_indicators += html_text[0:index]
            # Remove leading (link) indicator
            html_text = html_text[index + len(self.link_indicator):]
            # Look for middle (link) indicator
            index2 = html_text.find(self.link_indicator)
            if index2 == -1:
                raise RuntimeError("Missing link indicator after target, remaining html is: " + html_text)
            target = html_text[0:index2]
            # Remove middle (link) indicator
            html_text = html_text[index2 + len(self.link_indicator):]
            # Look for trailing (link) indicator
            index3 = html_text.find(self.link_indicator)
            if index3 == -1:
                raise RuntimeError("Missing link indicator after text, remaining html is: " + html_text)
            text = html_text[0:index3]
            # Remove trailing (link) indicator
            html_text = html_text[index3 + len(self.link_indicator):]
            # Add link href to output
            html_after_handling_link_indicators += ("<a href=\"" + target + "\">" + text + "</a>")
            # Look for leading (link) indicator
            index = html_text.find(self.link_indicator)
        html_after_handling_link_indicators += html_text
        output_html = ""
        for hc in html_after_handling_link_indicators:
            if ord(hc) >= 128:
                output_html += "&#" + str(ord(hc)) + ";"
            else:
                output_html += hc
        with self.create_file(file_name, "w") as fd:
            fd.write(self.html_prolog + output_html + self.html_epilog)


    def create_dir(self, dir_name):
        if os.path.exists(dir_name):
            if os.path.isdir(dir_name):
                if os.access(dir_name, os.W_OK) == False:
                    raise RuntimeError("You do not have write access to dir " + dir_name)
            else:
                raise RuntimeError(dir_name + " is not a directory")
        else:
            try:
                os.mkdir(dir_name)+++++++++++++++++++++++++++++++++++
            except IOError as err:
                raise RuntimeError(str(err) + " creating " +  dir_name)

def main():
    try:
        SLACK_TOKEN = os.environ.get('SLACK_TOKEN')
        slack_client = SlackClient(SLACK_TOKEN)
        slack_obj = Iima79SlackBack(slack_client, SLACK_TOKEN)
        run_datetime = datetime.datetime.today().strftime("%Y-%m-%d-%H-%M")
        run_label = "cull_de_slack-"+ run_datetime
        slack_obj.set_output_dir(os.path.join("/nobackup", run_label))
        slack_obj.set_run_label("")
        slack_obj.set_html_prefix("http://cbdasgupta.org/slackback/websaves/")
        print("Users...")
        slack_obj.process_users(["CLEAR", "GET","SAVE","RENDER"])
        print("Channels...")
        slack_obj.process_channels(["CLEAR", "GET","SAVE","RENDER"])
        print("Files...")
        slack_obj.process_files(["CLEAR", "GET","SAVE","RENDER"])
        slack_obj.create_index_file()
        slack_obj.set_merge_input_dirs(["/nobackup/cds-12-06-17"])
        slack_obj.set_output_dir(["/nobackup/websaves"])
        print("Merging Users...")
        slack_obj.process_users(["MERGE","RENDER"])
        print("Merging Channels...")
        slack_obj.process_channels(["MERGE","RENDER"])
        print("Merging Files...")
        slack_obj.process_files(["MERGE","RENDER"])
        slack_obj.create_index_file()
        print("Done.")
        #print ("Deleting messages 2017-03)")
        #slack_obj.delete_messages('2017-03')
        #print ("Deleting messages 2017-04)")
        #slack_obj.delete_messages('2017-04')
        #slack_obj.delete_files('2017-03')
    except RuntimeError as err:
        print err.msg
        sys.exit(1)

if __name__ == "__main__":
    main()
