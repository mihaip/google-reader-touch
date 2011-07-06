import getpass
import json
import time
import sys
import urllib
import urllib2

TAG_ID_PREFIX = 'tag:google.com,2005:reader/item/'
ITEM_IDS_CHUNK_SIZE = 10000
EDIT_TAG_CHUNK_SIZE = 100

TAGS = [
  'user/-/state/com.google/starred',
  'user/-/state/com.google/broadcast',
  'user/-/state/com.google/like',
  'user/-/source/com.google/post',
  'user/-/source/com.google/link',
  'user/-/state/com.google/read',
]

email = raw_input('Google Account username: ')
password = getpass.getpass('Password: ')

credentials_data = urllib.urlencode({
  'Email': email,
  'Passwd': password,
  'service': 'reader',
  'accountType': 'GOOGLE',
})
auth_response = urllib2.urlopen(
    'https://www.google.com/accounts/ClientLogin', credentials_data)

auth_token = None

for line in auth_response.readlines():
  key, value = line.strip().split('=', 1)
  if key == 'Auth':
    auth_token = value
    break
auth_response.close()

assert auth_token
auth_headers = {'Authorization': 'GoogleLogin auth=%s' % auth_token}

def ExecuteMethod(method, data=None, use_authentication=True):
  if data:
    if use_authentication:
      data += [('T', action_token)]
    request_data = urllib.urlencode(data)
  else:
    request_data = None

  request = urllib2.Request(
      'https://www.google.com/reader/api/0/%s' % method,
      data=request_data,
      headers=use_authentication and auth_headers or {})
  response = urllib2.urlopen(request)
  response_text = response.read()
  response.close()
  return response_text

action_token = ExecuteMethod('token')

last_touch_tag = None

for tag in TAGS:
  print 'Touching %s' % tag
  
  print '  Fetching item IDs...'
  item_ids = set()
  # The stream/items/ids endpoint doesn't support continuation tokens, so we
  # have to approximate them by passing in the timestamp of the last returned
  # item as the upper bound of items that we're willing to accept.
  last_item_timestamp = None
  while True:
    params = {
      's': tag,
      'n': ITEM_IDS_CHUNK_SIZE,
      'output': 'json',
    }
    if last_item_timestamp:
      params['nt'] = int(last_item_timestamp/1000000)
    method = 'stream/items/ids?' + urllib.urlencode(params)
    response_json = json.loads(ExecuteMethod(method))
    item_refs_json = response_json['itemRefs']
    
    # It's possible for responses to overlap (because of second/microsecond
    # precision issues), so we want to stop if we just get back a single item
    # that we've seen before.
    if not item_refs_json or (len(item_refs_json) == 1 and item_refs_json[-1]['id'] in item_ids):
      break

    print '    Got %d items' % len(item_refs_json)
    for item_ref_json in item_refs_json:
      item_ids.add(item_ref_json['id'])
    last_item_timestamp = long(item_refs_json[-1]['timestampUsec'])
    
  item_ids = list(item_ids)
  print '  Got %d items total' % len(item_ids)
  
  print '  Tagging items...'
  
  for i in xrange(0, len(item_ids), EDIT_TAG_CHUNK_SIZE):
    chunk_item_ids = item_ids[i:i + EDIT_TAG_CHUNK_SIZE]
    
    # Especially for read items, not all items are in the backend anymore, so
    # we first look up the contents before trying to tag them. Do this signed
    # out, so that we don't have to fetch the stream graph for these requests.
    item_id_params = []
    for item_id in chunk_item_ids:
      item_id_params.append(('i', item_id))
    try:
      item_contents_json = json.loads(ExecuteMethod(
          'stream/items/contents', item_id_params, use_authentication=False))
    except urllib2.HTTPError, e:
      print '    Got error %s for looking up chunk contents %s' % (str(e), str(chunk_item_ids))      

    found_item_ids = []
    item_id_params = []
    stream_id_params = []
    for item_content_json in item_contents_json['items']:
      item_id_params.append(('i', item_content_json['id']))
      stream_id_params.append(('s', item_content_json['origin']['streamId']))
      
      # The item contents response has IDs as base 16 unsigned longs, but the
      # item IDs gives them as signed base 10 longs, so we have to do some
      # munging to determine which are missing.
      item_id_unsigned = long(item_content_json['id'][len(TAG_ID_PREFIX):], 16)
      if item_id_unsigned < 1<<63:
        found_item_ids.append(str(item_id_unsigned))
      else:
        found_item_ids.append(str(item_id_unsigned - (1<<64)))
    if len(item_id_params) != len(chunk_item_ids):
      missing_item_ids = set(chunk_item_ids) - set(found_item_ids)
      print '    Warning, could only look up %d out of %d items in chunk %s, items most likely missing are: %s' % (
          len(item_id_params), len(chunk_item_ids), str(chunk_item_ids), missing_item_ids)
    
    try:
      touch_tag = 'user/-/state/com.google/touch-%s' % str(int(time.time())/(60 * 5))
      if touch_tag != last_touch_tag:
        print '[Touch tag is %s]' % touch_tag
        last_touch_tag = touch_tag

      ExecuteMethod('edit-tag', item_id_params + stream_id_params + [('a', touch_tag)])
      print '    Tagged %d (%d/%d) items' % (len(chunk_item_ids), i + len(chunk_item_ids), len(item_ids))
    except urllib2.HTTPError, e:
      print '    Got error %s for tagging chunk %s' % (str(e), str(chunk_item_ids))
