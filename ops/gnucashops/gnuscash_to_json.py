import sys
import xml.etree.ElementTree as ET
import json

def replace_url_by_ns_name(text):
  if text.startswith("{"):
    index = text.find("}")
    url = text[1:index]
    prefix = url.split("/")[-1]
    text = prefix + ":" + text[index + 1:]
  return text
  
def init(elem, tag_sequence, tag_sequences, act_guid_lookups, info_json):
  tag_to_use = replace_url_by_ns_name(elem.tag)
  tag_sequence = tag_sequence + "::" + tag_to_use
  attrib_list = ""
  for att in elem.attrib:
    attrib_list += "," + replace_url_by_ns_name(att)
  if tag_sequence + attrib_list not in tag_sequences:
        tag_sequences[tag_sequence + attrib_list] = ""

  if len(elem):

    parent_tag = tag_sequence.split("::")[-1]

    if parent_tag == "gnc:account":
      act_name = None
      act_guid_id = None
      act_cmdty_id = None
      act_cmdty_space = None
      act_info = {"type" : None, "cmdty_id__space" : None}

    if parent_tag == "gnc:commodity":
      cmdty_id = None
      cmdty_space = None

    if parent_tag == "gnc:transaction":
      trn_currency_id = None
      trn_currency_space = None
      trn_info = {"date-posted" : None, "date-entered" : None, \
          "description" : None, "currency_id__space" : None, "splits": []}

    for child in elem:

      child_tag_to_use = replace_url_by_ns_name(child.tag)

      if parent_tag == "gnc:account":
        if child_tag_to_use == "act:name":
          act_name = child.text
        elif child_tag_to_use == "act:type":
          act_info["type"] = child.text
        elif child_tag_to_use == "act:id"  and "type" in child.attrib and child.attrib["type"] == "guid":
          act_guid_id = child.text
        elif child_tag_to_use == "act:commodity":
          for grandchild in child:
            grandchild_tag_to_use = replace_url_by_ns_name(grandchild.tag)
            if grandchild_tag_to_use == "cmdty:id":
              act_cmdty_id = grandchild.text
            elif grandchild_tag_to_use == "cmdty:space":
              act_cmdty_space = grandchild.text
          if act_cmdty_id is not None and act_cmdty_space is not None:
            act_info["cmdty_id__space"] = act_cmdty_id + "__" + act_cmdty_space
        continue

      if parent_tag == "gnc:commodity":
        if child_tag_to_use == "cmdty:id":
          cmdty_id = child.text
        elif child_tag_to_use == "cmdty:space":
          cmdty_space = child.text
        continue
        
      if parent_tag == "gnc:transaction":
        if child_tag_to_use == "trn:date-posted":
          for grandchild in child:
            grandchild_tag_to_use = replace_url_by_ns_name(grandchild.tag)
            if grandchild_tag_to_use == "ts:date":
              trn_info["date-posted"] = grandchild.text
        if child_tag_to_use == "trn:date-entered":
          for grandchild in child:
            grandchild_tag_to_use = replace_url_by_ns_name(grandchild.tag)
            if grandchild_tag_to_use == "ts:date":
              trn_info["date-entered"] = grandchild.text
        elif child_tag_to_use == "trn:description":
          trn_info["description"] = child.text
        elif child_tag_to_use == "trn:currency":
          for grandchild in child:
            grandchild_tag_to_use = replace_url_by_ns_name(grandchild.tag)
            if grandchild_tag_to_use == "cmdty:id":
              trn_currency_id = grandchild.text
            elif grandchild_tag_to_use == "cmdty:space":
              trn_currency_space = grandchild.text
          if trn_currency_id is not None and trn_currency_space is not None:
            trn_info["currency_id__space"] = trn_currency_id + "__" + trn_currency_space
        elif child_tag_to_use == "trn:splits":
          for grandchild in child:
            if replace_url_by_ns_name(grandchild.tag) != "trn:split":
              continue
            split_info = {"value" : None, "quantity" : None, "reconciled-state" : None, "account" : None}
            for greatgrandchild in grandchild:
              greatgrandchild_tag_to_use = replace_url_by_ns_name(greatgrandchild.tag)
              if greatgrandchild_tag_to_use == "split:quantity":
                words = greatgrandchild.text.split("/")
                split_info["quantity"]= eval( "float(" + words[0] + ")/" + words[1])
              elif greatgrandchild_tag_to_use == "split:value":
                words = greatgrandchild.text.split("/")
                split_info["value"]= eval( "float(" + words[0] + ")/" + words[1])
              elif greatgrandchild_tag_to_use == "split:reconciled-state":
                split_info["reconciled-state"]= greatgrandchild.text
              elif greatgrandchild_tag_to_use == "split:account":
                split_info["account"]= greatgrandchild.text
            trn_info["splits"].append(split_info)
        continue
        
    if parent_tag == "gnc:account" and act_name is not None and act_guid_id is not None:
      act_guid_lookups[act_guid_id] = act_name
      info_json["accounts"][act_name] = act_info
    if parent_tag == "gnc:commodity" and cmdty_id is not None and cmdty_space is not None:
      info_json["cmdty_id__space"][cmdty_id + "__" + cmdty_space] = ""
    if parent_tag == "gnc:transaction":
      info_json["transactions"].append(trn_info)
      
    for child in elem:
      init(child, tag_sequence, tag_sequences, act_guid_lookups, info_json)

def replace_act_guids_by_names(info_json, act_guid_lookups):
  for transaction in info_json["transactions"]:
    for split in transaction["splits"]:
      if split["account"] in act_guid_lookups:
        split["account"] = act_guid_lookups[split["account"]]
      
tag_sequences = {}
act_guid_lookups = {}
info_json = { "accounts" : {}, "cmdty_id__space" : {}, "transactions": []}

if len(sys.argv) != 3:
  print("Usage: gnucash-xml output-json")
  exit(1)
tree = ET.parse(sys.argv[1])
init(tree.getroot(), "", tag_sequences, act_guid_lookups, info_json)
replace_act_guids_by_names(info_json, act_guid_lookups)
with open(sys.argv[2], "w") as fd:
  json.dump(info_json, fd, indent = 4)
