from django.shortcuts import render
from django.http import HttpResponse
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import random
import http.client
import urllib.request
import urllib.parse
import json
import hmac
import hashlib
import base64

accesskey="<accesskey>"
secretkey="<secretkey>"
environment="test"


remote_script="https://sandbox-payments.open.money/layer"

# For Production
# remote_script="https://payments.open.money/layer"

sample_data = dict()
sample_data["amount"] = "12.00"
sample_data["currency"] = "INR"
sample_data["name"] = "John Doe"
sample_data["email_id"]="john.doe@dummydomain.com"
sample_data["contact_number"]= "9831111111"
sample_data["mtx"]= ""
sample_data["empty"]=""

BASE_URL_SANDBOX = "sandbox-icp-api.bankopen.co";
BASE_URL_UAT = "icp-api.bankopen.co";					   

# Create your views here.
@csrf_exempt
def index(request):
	global accesskey,secretkey,environment,remote_script,sample_data
	error=""
	layer_payment_token_data=dict()
	payment_token_data = dict()
	token_id=""
	hash = ""
	layer_params=""
	sample_data["mtx"] = random.randint(1,200)
	
	
	layer_payment_token_data = create_payment_token(sample_data,accesskey,secretkey,environment)
	
	if layer_payment_token_data:
		for k in layer_payment_token_data.keys():
			if k == "error":
				error = layer_payment_token_data[k]
		
	if len(error) == 0 and len(layer_payment_token_data["id"]) < 1:
		error="E55 Payment error. Token data empty."
			
	if len(error) == 0 and len(layer_payment_token_data["id"]) > 0:
		payment_token_data = get_payment_token(layer_payment_token_data["id"],accesskey,secretkey,environment)
	
	if payment_token_data:		
		for k in payment_token_data.keys():
			if k == "error":
				error = payment_token_data[k]
				
	if len(error) == 0 and len(payment_token_data["id"]) < 1:
		error="Payment error. Layer token ID cannot be empty."
		
	if len(error) == 0 and len(payment_token_data["id"]) > 0 and payment_token_data["status"]=="paid": 
		error="Layer: this order has already been paid."
		
	if len(error) == 0 and str(payment_token_data["amount"]) != str(sample_data["amount"]): 
		error="Layer: an amount mismatch occurred."
		
	if error == "":
		gen = dict()
		gen["amount"]=payment_token_data["amount"]
		gen["id"]=payment_token_data["id"]
		gen["mtx"]=sample_data["mtx"]
		hash=create_hash(gen,accesskey,secretkey)		
		layer_params = "{payment_token_id:"+payment_token_data["id"]+",accesskey:"+accesskey+"}"
		token_id=payment_token_data["id"]
		
	
	return render(request,
	'layerpayment/checkout.html',
	{'txnid':str(sample_data["mtx"]),
	'fullname':sample_data["name"],
	'email':sample_data["email_id"],
	'mobile':sample_data["contact_number"],
	'amount':str(sample_data["amount"]),
	'currency':sample_data["currency"],
	'remote_script':remote_script,
	'token_id':token_id,
	'hash':hash,
	'accesskey':accesskey,
	'layer_params':layer_params,
	'error':error})

@csrf_exempt	
def callback(request):
	global accesskey,secretkey,environment
	error=""
	status=""
	payment_data=dict()
	
	response = request.POST
	if len(response["layer_payment_id"]) == 0:
		error = "Invalid payment id"
	if len(error)==0:
		vhash=dict()
		vhash["amount"] =response["layer_order_amount"]
		vhash["id"]=response["layer_pay_token_id"]
		vhash["mtx"]=response["tranid"]
		if not verify_hash(vhash,response["hash"],accesskey,secretkey):
			error="Invalid payment response...Hash mismatch"
	if len(error) == 0:
		payment_data = get_payment_details(response["layer_payment_id"],accesskey,secretkey,environment)
	
	if payment_data:
		for k in payment_data.keys():
			if k == "error":
				error = payment_data[k]
	if len(error) == 0 and payment_data["payment_token"]["id"] != response["layer_pay_token_id"]:
		error = "Layer: received layer_pay_token_id and collected layer_pay_token_id doesnt match"
	if len(error) == 0 and payment_data["amount"] != response["layer_order_amount"]:
		error = "Layer: received amount and collected amount doesnt match"
	if len(error) == 0 and payment_data["payment_token"]["status"] != "paid":
		status = "Transaction failed..."+payment_data["payment_error_description"]
	elif len(error) == 0:
		status = "Transaction Successful"
	
	return render(request,
	'layerpayment/response.html',
	{'errorstring':error,
	 'status':status})
	


def create_payment_token(data,accesskey,secretkey,environment):
	response=dict()
	
	try:
		emptykeys=[]
		for k in data.keys():
			if len(str(data[k]))<1:
				emptykeys.append(k)
		for i in emptykeys:
			del data[i]
		response = http_post(data,"payment_token",accesskey,secretkey,environment)
	except Exception as ex:			
		response["error"]=ex
	
	return response
	

def get_payment_token(payment_token_id,accesskey,secretkey,environment):
	response=dict()
	try:
		if len(payment_token_id)==0 or payment_token_id.isspace():
			response["error"]="payment_token_id cannot be empty"				
		else:
			response = http_get("payment_token/" + payment_token_id,accesskey,secretkey,environment)
	except Exception as ex:
		response["error"] = ex
	
	return response
	

def get_payment_details(payment_id,accesskey,secretkey,environment):
	response=dict()
	try:
		if len(payment_id)==0 or payment_id.isspace():			
			response["error"]="pyment_id cannot be empty"	
		else:
			response=http_get("payment/"+payment_id,accesskey,secretkey,environment)
	except Exception as ex:
		response["error"] = ex
	
	return response
	

def http_post(data,route,accesskey,secretkey,environment):
	response = ""
	url = BASE_URL_SANDBOX 
	if environment == "live":
		url = BASE_URL_UAT 
	
	resource = "/api/"+route
	
	try:
		conn = http.client.HTTPSConnection(url,timeout=10)
		headers = {'Content-type': 'application/json',"Authorization":"Bearer "+accesskey+":"+secretkey}
		jdata = json.dumps(data)
		conn.request('POST', resource, jdata, headers)
		resp = conn.getresponse()		
		rdata = resp.read().decode('utf-8')
		conn.close()
		response = json.loads(rdata)		
	except Exception as ex:
		print(ex)
	
	return response
	
def http_get(route,accesskey,secretkey,environment):
	response = ""
	url = BASE_URL_SANDBOX 
	if environment == "live":
		url = BASE_URL_UAT 
	resource = "/api/"+route
	
	try:
		conn = http.client.HTTPSConnection(url,timeout=10)
		headers = {'Content-type': 'application/json',"Authorization":"Bearer "+accesskey+":"+secretkey}
		conn.request("GET", resource,"",headers)
		resp = conn.getresponse()
		rdata = resp.read().decode('utf-8')
		conn.close()
		response = json.loads(rdata)
	except Exception as ex:
		print(ex)
	
	return response
	
	
def create_hash(data,accesskey,secretkey):
	hash=""
	try:
		pipeSeperatedString=accesskey+"|"+str(data["amount"])+"|"+data["id"]+"|"+str(data["mtx"])
		signature = hmac.new(
			bytes(secretkey , 'latin-1'),  
			msg = bytes(pipeSeperatedString , 'latin-1'), 
			digestmod = hashlib.sha256).hexdigest().upper()
		
		base64_bytes = base64.b64encode(signature.encode('ascii'))
		hash = base64_bytes.decode('ascii')
		 
	except Exception as ex:
		hash = ex
		
	return hash
	

def verify_hash(data,rec_hash,accesskey,secretkey):
	gen_hash = create_hash(data,accesskey,secretkey)
	if gen_hash == rec_hash:
		return True
	else:
		return False
	
