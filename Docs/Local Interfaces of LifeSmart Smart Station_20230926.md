> 1

# Local Interfaces of LifeSmart Smart Station 

Version Revision Date Revised By Description 

1.0 2019/06/03 Ye Zhengqiang This document is prepared according 

to LifeSmart's third-party access rules. 

1.1 201 9/11/26 Ye ZhengQiang OpenDev adds backup, restore 

interfaces 

1.2 20 20 /08/11 Ye ZhengQiang 

OpenDev Adds Smart Station version 

query interface, upgrade interface, 

device renaming interface, refer to 

3.3.10 Smart Station configuration 

commands (upgrade, devname, 

getver) 

1.3 20 20 /11/10 Ye ZhengQiang 

OpenDev Smart Station version query 

interface adds Smart Station type and 

system version response. Smart 

Station adds Defed series devices, 

refer to 6.11 Defed series for details 

1.4 20 20 /11/10 Ye ZhengQiang OpenDev arranging 

1.5 20 22 /06/18 Ye ZhengQiang 

1.add devices 

2.Extended Smart Station upgrade 

interface 

1.6 2022/08/04 Ye ZhengQiang 1.add devices 

2.Extended 485 Device Properties 

1. 7 20 22 /12/01 Ye ZhengQiang 1. add devices (marked in yellow) 

1. 8 20 23 /01/04 Ye ZhengQiang 

1. add lDbm Device 

Propert y(marked in yellow) 

2. add Eliq device (marked in yellow) 

1.9 2023/05/11 Ye ZhengQiang 

3.3.2 Obtain a list of smart station sub 

devices 

3.3.7 Add smart station sub devices 

(only for CoSS devices) 

3.3.9 Obtaining the signal value of 

smart station sub equipment 2   

> 1.10 2023/09/15 Ye ZhengQiang

3.3.7 Adding smart station Sub-

Devices (CoSS Devices only) Added 

the exargs parameter 

6.1 Attributes shared by sub devices 

Added epver 

6.7 Unique properties of smart door 

locks Add several new devices 3

# Contents 

1. Introduction ............................................................................................................... 1

1.1 Interface Enabling Process - App Enabling .............................................................................. 1

1.2 Interface Enabling Process - Scanning Code for Enabling ....................................................... 2

2. Discovery Protocol .......................................................................................................... 3

3. API Protocol ............................................................................................................... 3

3.1 Message Format ..................................................................................................................... 4

3.1.1 Request Data Format .................................................................................................... 5

3.2 Signature Security Algorithm ................................................................................................... 5

3.2.1 Signature Algorithm ....................................................................................................... 6

3.3 API Description ...................................................................................................................... 7

3.3.1 Obtaining Information About a Single Sub-device of the Smart Station .......................... 7

3.3.2 Obtaining the Sub-device List of the Smart Station ........................................................ 8

3.3.3 Controlling a Single Sub-device of the Smart Station ..................................................... 9

3.3.4 Controlling Multiple Sub-devices of the Smart Station .................................................. 10 

3.3.5 Obtaining the Scene List of the Smart Station .............................................................. 11 

3.3.6 Triggering a Single Scene of the Smart Station ........................................................... 12 

3.3.7 Adding a Sub-device of the Smart Station (Applicable to CoSS Devices Only) ............ 13 

3.3.8 Removing Sub-devices from the Smart Station ............................................................ 15 

3.3.9 Obtaining Signal Value of the Sub-device of the Smart Station .................................... 16 

3.3.10 Configuration Commands of the Smart Station .......................................................... 17 

4. Local Event Service ...................................................................................................... 21 

4.1 Event Attribute Description .................................................................................................... 21 

5. Scenes ............................................................................................................. 22 

5.1 Scene Query Attribute Description ......................................................................................... 22 

5.2 Scene Triggering Attributes ................................................................................................... 22 

6. Sub-device ............................................................................................................. 23 

6.1 Common Attributes of Sub-devices ........................................................................................ 23 

6.2 Attributes Specific to Sockets ................................................................................................ 24 

6.2.1 Traditional Sockets ...................................................................................................... 24 

6.2.2 Metering Socket ...................................................................................................... 24 

6.3 Attributes Specific to Switches ............................................................................................... 25 

6.3.1 Traditional Switch ...................................................................................................... 25 

6.3.2 Stellar Switch/Sterry Switch/Polar Switch .................................................................... 26 

6.3.3 Polar Switch (LN) ...................................................................................................... 27 

6.3.4 Moonstone Switch ...................................................................................................... 27 

6.3.5 Stellar Switch/Sterry Switch/Polar Multi-control Accessory .......................................... 28 

6.3.6 CUBE Clicker(old version) ........................................................................................... 29 

6.3.7 CUBE Clicker (new version) ........................................................................................ 30 

6.3.8 CUBE Switch Module .................................................................................................. 30 

6.3.9 Nature Mini/Nature Mini S/Nature Mini L/Nature Mini Pro (as switch) ............................ 30 

6.3.10 Smart Remote Controller ........................................................................................... 31 

6.4 Attributes Specific to Curtain Controllers ................................................................................ 31 

6.4.1 Curtain Control Switch ................................................................................................. 31 

6.4.2 DOOYA Curtain Motor ................................................................................................. 32 

6.4.3 MINS Curtain Motor Controller .................................................................................... 33 4

6.5 Attributes Specific to Lighting Devices ................................................................................... 33 

6.5.1 Light Strip and Bulb ..................................................................................................... 33 

6.5.2 SPOT ...................................................................................................... 35 

6.5.3 Lights Series ...................................................................................................... 39 

6.6 Attributes Specific to Sensors ................................................................................................ 41 

6.6.1 Door Sensors ...................................................................................................... 41 

6.6.2 Dynamic Sensor ...................................................................................................... 41 

6.6.3 Environmental Sensor ................................................................................................. 42 

6.6.4 Water Leak Sensor ...................................................................................................... 42 

6.6.5 Gas Sensor (Formaldehyde) ....................................................................................... 43 

6.6.6 Gas Sensor (Gas) ...................................................................................................... 43 

6.6.7 Environmental Sensor (TVOC+CO2) ........................................................................... 44 

6.6.8 Smoke Sensor ...................................................................................................... 45 

6.6. 9 Environmental Sensor (CO2) ....................................................................................... 45 

6.7 Attributes Specific to Smart Door Locks ................................................................................. 46 

6.7.1 Smart Door Locks ...................................................................................................... 46 

6.7. 2 C100/C200 Door Locks ............................................................................................ 49 

6.8 Attributes Specific to Temperature Controllers ....................................................................... 51 

6.8.1 HVAC Controller ...................................................................................................... 51 

6.8.2 Control Panel of HVAC Controller ................................................................................ 51 

6.8.3 Underfloor Thermostat ................................................................................................. 52 

6.8.4 Fan Coil Thermostat .................................................................................................... 54 

6.8.5 Air Conditioner Control Panel ...................................................................................... 55 

6.8.6 Nature Mini Pro(Thermostat) ....................................................................................... 59 

6.8.7 Nature Thermostat ...................................................................................................... 59 

6.8.8 Thermostatic Radiator Valve ........................................................................................ 62 

6.8.9 HVAC Smart Controlle r- ventilation .............................................................................. 63 

6.9 Attributes Specific to General Controller ................................................................................ 65 

6.9.1 General Controller ...................................................................................................... 65 

6.9.2 485 Controller ...................................................................................................... 68 

6.9.3 DLT Smart Plug ...................................................................................................... 68 

6.9. 4HA Interface Adapter （JEMA) ....................................................................................... 69 

6.9. 5 Status Indicator ...................................................................................................... 71 

6.9. 6 Eliq Electricity meter ...................................................................................................... 71 

6.10 Attributes Specific to Smart Station MINI ............................................................................. 72 

6.10.1 Built-in Alarm of the Smart Station MINI ..................................................................... 72 

6.11 Defed Series ........................................................................................................................ 73 

6.11.1 Defed PIR Sensor ...................................................................................................... 73 

6.11.2 Defed Door/window sensor ........................................................................................ 73 

6.11.3 Defed Keyfob ............................................................................................................. 74 

6.11.4 Defed Indoor Siren ..................................................................................................... 74 

7. Appendix ............................................................................................................. 75 

7.1 Smart Devices .................................................................................................................... 75 

7.2 Dynamic Color (DYN) Definition ............................................................................................. 77 1

# 1. Introduction 

The LifeSmart Smart Station series devices provide interface services (OpenDev) to allow local 

query and control by third parties so that they can operate and manage the smart devices 

connected to the Smart Station. The channels for local query and control are carried over UDP and 

the interaction mode is request-answer. In addition, in order to ensure connection security and 

perform access control, all requests must comply with the signature rules of the local interfaces of 

the Smart Station. The services consist of the discovery service, interface service, and event 

service. 

This section describes 2 ways about how to enable interfaces. You only can enable either of the 

two interfaces. 

# 1.1 Interface Enabling Process - App Enabling 

Before a third-party app uses the local interface service (OpenDev), apply for the device model, 

token, and key (encrypt) from LifeSmart. Then, configure the OpenDev smart template via the 

LifeSmart app for the third-party app so as to enable the Smart Station to provide services. The 

following describes how to configure the smart template: 

(1) Select the Smart tab on the homepage. Then, touch the + button. The page shown in Figure 1

is displayed. 2

Figure 1 Figure 2

(2) Choose Smart Template Management and touch Add Template. The page shown in Figure 2

is displayed. 

(3) Choose Common Templates, enter OpenDev to search for templates, and touch the OpenDev 

template to begin configuration. The page shown in Figure 3 is displayed. 

Figure 3 Figure 4

(4) Choose Edit List Mode. On the page shown in Figure 4, set the name, model, token, and 

encrypt and then return to the previous page. Then, touch the "tick" button to finish the 

configuration. If no error is displayed, the configuration is successful. 

(5) When the OpenDev interface enabled via the app is used to provide services in UDP mode, 

the third-party app uses port 12346 to receive requests and send responses. 

# 1.2 Interface Enabling Process - Scanning Code for Enabling 

Before a third-party app uses the local interface service (OpenDev), apply for the device model, 

token, and encrypt from LifeSmart, and provide the QR code for enabling. 

(1) The third party app user upgrades the Smart Station to the latest official version via the 

LifeSmart app. 3

(2) The user uses the scanning function of the LifeSmart app to scan the code and selects the 

Smart Station to be configured. If the account has only one Smart Station, skip the selection. 

(3) After the scanning is successful, the app will prompt the user for confirmation and deliver 

configurations. After checking the configurations, the user touches OK. 

(4) Then, the user restarts the Smart Station. After the restart succeeds, the user selects the 

function of viewing all devices. A device whose name is the same as the configured one is 

displayed in the Smart Station, indicating that the configuration is successful. 

(5) When the OpenDev interface enabled by using the scanning function is used to provide 

services in UDP mode, the third-party app does not have to only use port 12346 to receive 

requests and send responses. 

# 2. Discovery Protocol 

When the local interface service of the Smart Station is used, the third-party device and the 

LifeSmart Smart Station communicate with each other in the local area network. The Smart Station 

broadcasts UDP messages to search and discover the third-party device. 

After receiving the UDP broadcast messages, the third-party device responds with the device 

information. The data packets carry UTF8-encoded text strings. 

In the response message of the third-party device, MOD indicates the model applied, and NAME 

indicates the device name. SN indicates the unique serial number of the device, which can be the 

MAC address of the device. VER indicates the device version. New keys can be added. They are 

separated by '\n'. 

Note: 

By receiving the UDP broadcast messages, a third-party device can determine the IP address of 

the LifeSmart Smart Station for subsequent communications. 

When the Smart Station is enabled by scanning code, the third-party device does not need to reply. 

Protocol UDP 

Port No. 12345 

Message type Broadcast message 

Broadcast command 

word Z-SEARCH * \r\n 

Message returned by 

the third-party device MOD=xxxx\nSN=xxxx\nNAME=xxxx\nVER=xxxx\n 

Third party devices can also obtain a list of LifeSmart smart stations within the local area network 

through broadcast messages. 

The LSID in the smart station echo message is the unique id of the smart station , MGAMOD is the 

type of smart station , and other keys can currently be ignored, separated by the character ' n'. 4

Protocol UDP 

Port No. 12345 

Message type Broadcast message 

Broadcast command 

word Z-SEARCH * \r\n 

Message returned by 

the smart station LSID=xxxx\nMGAMOD=xxxx\nWLAN=xxxx\nNAME=xxxx\n 

# 3. API Protocol 

Interface services use UDP for communications. The Smart Station uses port 12348 to receive 

interface requests. After the processing is completed, results are returned. 

Note: 

The Smart Station enabled by the App returns responses to port 12346 of the third-party device. 

The Smart Station enabled by scanning code returns responses to the sending port of the third-

party device. 

Control requests and pairing requests are sent over the synchronization interface. Results are 

returned only after the request processing is completed. 

Network 

protocol UDP UDP 

Object Smart Station Device 

Port No. 12348 12346 

Description The device sends requests to port 12348 

of the Smart Station. 

The Smart Station returns responses 

to port 12346 of the device. 

# 3.1 Message Format 

The message of the local interface protocol of the Smart Station consists of two parts: the 10-byte 

header and the body of JSON string, as shown in the following table. 

Name Description Length 

(Byte) 

Type Remarks 

header Message 

start 

identifier 

2 String JL: Normal 

version Protocol 

version 

number 

2 Integer The default value is 0. 

pkg_type Message 

type 

2 Integer 0: Reserved 

1: GET 5

2: GET-REPLY 

3: SET 

4: SET-REPLY 

5: ADD 

6: ADD-REPLY 

7: DELETE 

8: DELETE-REPLY 

9: NOTIFY 

10: NOTIFY-REPLY 

pkg_size Body length 4 32-bit unsigned 

integer 

content Body pkg_size UTF-8 encoded 

string 

The content is in JSON format. 

# 3.1.1 Request Data Format 

The message body carries request data in JSON format. The data structure is as follows: 

sys 

ver Protocol version, number 1

sign Signature value. See 3.2.1 Signature Algorithm. 

model Device model 

ts UTC timestamp. The time is after January 1, 

1970 and in the unit of second. 

obj Object name 

args 

<attr>:<val>, 

…

<attr>:<val> 

Set of parameters used by the HTTP method 

id Message serial number 

sys: sys parameter meaning 

 ver: protocol version number. Currently, it is fixed to number 1. 

 sign: signature value. It is used by the server for signature verification, and the signature 

algorithm is described in 3.2 Signature Security Algorithm. 

 model: the model obtained when the third-party module is registered 

 ts: timestamp of request (UTC), time of the zero-time zone 

obj: For details about the currently supported objects, see 3.3 API Interfaces. 

args: Object-specific parameters need to be input. For details, see 3.3 API Interfaces. 

id: message ID. The ID of a response message is consistent with the ID of its request message. 

# 3.2 Signature Security Algorithm 

To ensure the security of communications between third-party devices and the Smart Station, this 

protocol requires that all requests in JSON format should carry the signature information of the 

request source. The signature value is assigned to the sign parameter in the sys parameter set of 6

the JSON requests. 

After receiving a request, the Smart Station first checks the ts timestamp information carried in the 

JSON request. If the difference between the timestamp and the local time of the Smart Station is 

greater than 5 minutes, the request packet is considered invalid and an error code is returned. 

If the timestamp checking passes, the sign signature value is verified by using the unified signature 

algorithm. A JSON request is accepted only when the signature value is consistent. 

To implement the above security mechanism, the user must communicate with LifeSmart first to 

obtain the model and token of the local interface of the Smart Station before connecting the third-

party device to the Smart Station. 

# 3.2.1 Signature Algorithm 

The detailed procedure of the signature algorithm is as follows: 

(1) Calculate the "original signature string": Original signature string = obj + args parameter set 

(all fields are sorted in ascending order and then all field names and corresponding values are 

input) + ts string in the sys parameter set + model + token. The following is an example. 

obj:<obj>,<arg>:<val>, …,< arg >:<val>,ts:<val>,model:<val>,token:<val> 

(2) The "original signature string" is processed based on MD5 and converted into a hexadecimal 

32-bit lowercase string, which is used as the signature value sign. 

Note: 

The model and token are assigned by LifeSmart and used together. 

If the args parameter is in array or list format, this parameter is not used during signature 

calculation. 

Example: 

Request: 

{

"id": 1,

"args": {

"tag": "03" ,

"me": "80fa" ,

"idx": "L1" ,

"type": 128 ,

"val": 0,

}

"obj": "ep" ,

"sys": {

"ver": 1,

"ts": 1571976095 ,

"sign": "dbe2076ba2a67fe886aa5098d165ac7a" ,

"model": "OD_XXX_XXX" 7

}

}

Original signature string: 

obj:ep,idx:L1,me:80fa,tag:m,type:128,val:0,ts:1571976095,model:OD_XXX_XXX,token:token1234 

56token123456 

# 3.3 API Description 

In the interface description, the Smart Station is referred to as station, agent, or agt. The devices 

connected to the Smart Station, for example, sockets and temperature-humidity sensors, are 

referred to as ep. Third-party devices are referred to as Device. 

This section briefly describes the APIs supported by the OpenDev interface request service and 

provides request examples and returned values for reference. 

Note: For details about the device type and attribute parameters, see 6. Sub-devices. For details 

about scene type and parameter meaning, see 5. Scenes. 

# 3.3.1 Obtaining Information About a Single Sub-device of the Smart 

# Station 

obj ep 

Pkg_type GET 

Direction Device->Station 

Request {

"id": 2,

"args": {

"me": "2711" ,

}

"obj": "ep" ,

"sys": {

"ver": 1,

"ts": 1571976095 ,

"sign": "dbe2076ba2a67fe886aa5098d165ac7a" ,

"model": "OD_XXX_XXX" 

}

}

Response {

"code": 0,

"id": 2,

“agtid": "mga" ,

"msg": {

"stat": 1,

"data": {8

"L1": {

"valts": 0,

"v": 0

}

}, 

"agt": "mga" ,

"devtype": "SL_OL_3C" ,

"name": "2711" ,

"me": "2711" 

}

}

# 3.3.2 Obtaining the Sub-device List of the Smart Station 

obj eps 

Pkg_type GET 

Direction Device -> Station 

Request {

"id ": 1,

"args ": {

},

"obj ": "eps ",

"sys ": {

"ver ": 1,

"ts ": 1571976095 ,

"sign ": "dbe2076ba2a67fe886aa5098d165ac7a" ,

"model ": "OD_XXX_XXX "

}

}9

Response {

"code": 0,

"id": 1,

"agt id": "mga" ,

"msg ": [

{

"stat": 1,

"data": {

"L1 ": {

"valts": 0,

"v": 0

}

}, 

"agt": "mga" ,

"devtype": "SL_OL _3C ",

"name": "2711" ,

"me": "2711" 

}, 

{

"stat": 1,

"data": {

"O": {

"valts": 0,

"v": 0

}

}, 

"agt": "mga" ,

"devtype" : “SL_OL _3C ",

"name": "2713" ,

"me": "2713" 

}

]

}

Args Degree: Device list level, optional parameter, parameter type value 

[0, 1, 2]. When the parameter exists and is equal to 0 or 1, the 

returned device list will not contain data (sub device exclusive 

attribute), and the parameter defaults to 2; 

# 3.3.3 Controlling a Single Sub-device of the Smart Station 

Obj ep 

Pkg_type SET 

Direction Device->Station 

Request {

"id": 2,

"args": {

"tag": "m" ,10 

"me": "2711" ,

"idx": "L1" ,

"type": 128 ,

"val": 0,

}

"obj": "ep" ,

"sys": {

"ver": 1,

"ts": 1571976095 ,

"sign": "dbe2076ba2a67fe886aa5098d165ac7a" ,

"model": "OD_XXX_XXX" 

}

}

Response {

"code": 0,

"id": 2,

“agtid": "mga" ,

"msg": {

}

}

# 3.3.4 Controlling Multiple Sub-devices of the Smart Station 

obj eps 

Pkg_type SET 

Direction Device->Station 

Request {

"id": 2,

"args": [

{

"tag": "m" ,

"me": "2713" ,

"idx": "O" ,

"type": 129 ,

"val": 1,

}, 

{11 

"tag": "m" ,

"me": "2711" ,

"idx": "L1" ,

"type": 128 ,

"val": 0,

}, 

], 

"obj": "eps" ,

"sys": {

"ver": 1,

"ts": 1571976095 ,

"sign": "dbe2076ba2a67fe886aa5098d165ac7a" ,

"model": "OD_XXX_XXX" 

}

}

Response {

"code": 0,

"id": 2,

“agtid": "mga" ,

"msg": {

}

}

# 3.3.5 Obtaining the Scene List of the Smart Station 

obj scene 

Pkg_type GET 

Direction Device->Station 

Request {

"id": 2,

"args": {

}, 

"obj": "scene" ,

"sys": {

"ver": 1,

"ts": 1571976095 ,

"sign": "dbe2076ba2a67fe886aa5098d165ac7a" ,12 

"model": "OD_XXX_XXX" 

}

}

Response {

"code": 0,

"id": 2,

“agtid": "mga" ,

"msg": [

{

"id": “AI1571987214" ,

"desc": "scene" ,

"cls": "scene" ,

"name": "2711" 

}, 

{

"id": “AI1571987314" ,

"desc": "groupirc" ,

"cls": "groupirc" ,

"name": "2711" 

}

]

}

# 3.3.6 Triggering a Single Scene of the Smart Station 

obj doscene 

Pkg_type SET 

Direction Device->Station 13 

Request {

"id": 2,

"args": {

"id": “AI1571987214" ,

"args": {

"type": 128 ,

}

}, 

"obj": "doscene" ,

"sys": {

"ver": 1,

"ts": 1571976095 ,

"sign": "dbe2076ba2a67fe886aa5098d165ac7a" ,

"model": "OD_XXX_XXX" 

}

}

Response {

"code": 0,

"id": 2,

“agtid": "mga" ,

"msg": {

}

}

# 3.3.7 Adding a Sub-device of the Smart Station (Applicable to CoSS 

# Devices Only) 

Obj dopair 

Pkg_type SET 

Direction Device->Station 

Request {

"id": 2,

"args": {

}, 

"obj": "dopair" ,

"sys": {

"ver": 1,14 

"ts": 1571976095 ,

"sign": "dbe2076ba2a67fe886aa5098d165ac7a" ,

"model": "OD_XXX_XXX" 

}

}

Response {

"code": 0,

"id": 2,

“agtid": "mga" ,

"msg": {

}

}

Args Period: The timeout period for pairing CoSS protocol sub devices. If left 

blank, it defaults to 20 seconds; 

Chn: Pairing special CoSS protocol sub devices needs to be filled in and 

paired with bps; 

Bps: Pairing special CoSS protocol sub devices needs to be filled in and 

matched with chn; 

The required chn/bps devices are as follows: 

The parameter is set to {chn=1, bps=0x73}, 

Support device types 

SL_ SW_ ND1/SL_ SW_ ND2/SL_ SW_ ND3 (Star, Chenxing Switch 

Series) 

SL_ MC_ ND1/SL_ MC_ ND2/SL_ MC_ ND3 (Star, Chenxing Switch 

Companion Series) 

SL_ SW_ NS1/SL_ SW_ NS2/SL_ SW_ NS3 (Star Jade Switch Series 

Lower Left Button Paired Version) 

SL_ SW_ BS1/SL_ SW_ BS2/SL_ SW_ BS3 (Polar Star Switch 120 Zero 

Fire Series) 

SL_ SW_ MJ1/SL_ SW_ MJ2/SL_ SW_ MJ3 (Singularity Switch Module 

Series) 

SL_ LK_ LS_ V3 (Special Requirements Version Intelligent Door Lock) 15 

SL_ DF_ BB/SL_ DF_ GG/SL_ DF_ MM/SL_ DF_ SR (Defed series) 

SL_ R_ B (Intelligent Scene Remote Control)/SL_ P_ IR (Super Bowl Mini 

Edition) 

SL_ SW_ WW (0-10V 86 dimmer switch) 

SL_ CP_ VL (Heating Temperature Control Valve) 

Note: The value of chn/bps can be set to {chn={false, 1}, bps={false, 

0x3}}, indicating that both special parameter devices and non special 

parameter devices are allowed to be added during pairing; 

The format of the exargs parameter is exargs={value=0}. The parameter 

mainly changes value, and its value is an integer: 

exargs parameter example: 

SL_LK_SWIFTE-

>value=0(speed),value=0x22(powersaving),value=0xff(remote disabled) 

# 3.3.8 Removing Sub-devices from the Smart Station 

obj remove 

Pkg_type SET 

Direction Device->Station 

Request {

"id": 2,

"args": {

"me": "2711" ,

}, 

"obj": "remove" ,

"sys": {

"ver": 1,

"ts": 1571976095 ,

"sign": "dbe2076ba2a67fe886aa5098d165ac7a" ,

"model": "OD_XXX_XXX" 

}

}

Response {

"code": 0,16 

"id": 2,

“agtid": "mga" ,

"msg": {

}

}

# 3.3.9 Obtaining Signal Value of the Sub-device of the Smart Station 

obj rssi 

Pkg_type GET 

Direction Device->Station 

Request {

"id": 2,

"args": {

"me": "2711" ,

}, 

"obj": "rssi" ,

"sys": {

"ver": 1,

"ts": 1571976095 ,

"sign": "dbe2076ba2a67fe886aa5098d165ac7a" ,

"model": "OD_XXX_XXX" 

}

}

Response {

}

"code": 0,

"id": 2,

"agtid": "mga" ,

"msg": {

"noise": 29 ,

"fromrssi": 145 ,

"torssi": 155 ,

}

Args Me: the id of subdevices 

If there is no is in me,means getting the rssi of GW 

Response Meaning of returned data: 17 

Msg noise : indicates the value of the background noise. The lower the value, 

the better. 

fromrssi : indicates the strength of the signals sent by the Smart Station to 

the sub-devices. The higher the value, the better. 

torssi : indicates the strength of the signals sent by the sub-devices to the 

Smart Station. The higher the value, the better. 

Error code 102 indicates that the signal request fails. 

Other error codes indicate that request commands are incorrect. 

For devices powered by battery , only 102 will be returned. To obtain the 

signal value of the devices powered by battery , please use get-eps or get-

ep to obtain the lDbm attribute of the sub-device to obtain the signal 

strength value of the device. Therefore, battery devices can only obtain 

the signal strength from the sub-device to the smart station, and cannot 

obtain "noise" and "fromrssi" 

Conversion formula between LifeSmart RSSI value and dbm :

RF_Input_Level_dBm =(RSSI_value /2)-MODEM RSSI_COMP -70 

MODEM_RSSI_COMP = 0x40 = 64d is appropriate for most applications .

RSSI_value should be between 0 and 255. However, it cannot reach 255. 

Generally, it reaches up to 220 .

# 3.3.10 Configuration Commands of the Smart Station 

obj config 

Pkg_type SET 

Direction Device->Station 

Request {

"id": 2,

"args": {

"cfg": "reboot" ,

}, 

"obj": "config" ,18 

"sys": {

"ver": 1,

"ts": 1571976095 ,

"sign": "dbe2076ba2a67fe886aa5098d165ac7a" ,

"model": "OD_XXX_XXX" 

}

}

Response {

"code": 0,

"id": 2,

"agtid": "mga" ,

"msg": {

}

}

Args The current SET-> config commands include the following: 

cfg:reboot —> Controls the restart of the Smart Station. No additional 

parameters are required. 

cfg:reset —> Restores the factory settings of the Smart Station and 

restarts it. No other parameters are required, and the gateway is not 

used. 

cfg:notify —> Configures the OpenDev event service of the Smart Station. 

You need to add the parameters host and port . The host parameter is 

the IP address of the device receiving the event, and the port parameter 

is the port receiving the event. 

cfg:airctrl —> Configures the search panel of the HVAC controller under 

the Smart Station. You need to add the parameters me (mandatory), 

addr (mandatory), pval (mandatory), x (optional), and y (optional). 

The me parameter is the address of the HVAC controller, and the device 

type is SL_TR_XX. 

The addr parameter is the address to be searched. The value range is (0-

255), and it is usually set to 1. 

The pval parameter is the val value of the P1 attribute of the HVAC 

controller, which is used to distinguish the type of the central air 

conditioning system. Currently, only two types are supported, that is, the 

low 24-bit values of pval are 0x000001 and 0x000002. 19 

When the low 24-bit value of pval is 0x000002, the x and y values are 

mandatory. The value of x is a group value and the range is 0-3. The 

value of y is a channel value, and the range is 0-254. 

Note: 

If the number of air conditioner panels, group value, and channel value 

are unknown when the HVAC controller is used for the first time, the addr 

values need to be tried one by one. When the low 24-bit value of pval is 

0x000002, it is necessary to use the x and y values and make tries one 

by one. 

If there is no master control panel for the HVAC controller, a master 

control panel will be created when the call is successful, for example, 

(80fa:255_255@1). 

cfg:getver -> get the current version number of the Smart Station, no 

other parameters are required. 

cfg:devname -> set the name of the Smart Station or the sub-device 

under the Smart Station, required parameter name, optional parameter 

me, me is a string indicating the sub-device, me parameter does not exist 

means configure the name of the Smart Station itself. 

cfg:upgrade -> upgrade and download the Smart Station software 

package, no other parameters are required, the Smart Station needs to 

be restarted after the upgrade before the latest version will take effect, the 

software package will obtain the latest official version of the software 

package from the LifeSmart server. 

The optional parameters are as follows: reboot (optional), url (optional), 

info (to be used with url) 

reboot: Automatically restarts the Smart Station after a successful 

download of the package; 

url: other download address of the Smart Station package, http address, 

and must be used with the info parameter; 

info: contains the signature and MD5 information of the Smart Station 

package and the entire contents of the tar.gz.md5 file. It must be used 

with the url parameter; 20 

cfg:timezone -> set the timezone of the Smart Station and whether it is 

daylight saving time, parameter description:timezone(optional), 

summer(optional), timezone is the time zonen whose range is [-12,12], -

12 is west 12, 12 is east 12; summer is whether daylight saving time, 

boolean variable, true or false; when timezone and summer are empty it 

can be used as a view of the current time zone and daylight saving time 

status. .

Response Meaning of returned data: 

Msg reboot : If the result is success, msg {} is empty. 

reboot : If the result is success, msg {} is empty. 

notify : If the result is success, msg {} is {time=1572000773}. time is the 

system time of the Smart Station (UTC). 

airctrl : If the result is success, msg {} is {panel=["80fa:0_1@1"]}. panel is 

the list of identified panels. 

If error codes other than 0 are returned, request errors occur. 

getver : the ver in success msg means version number, mgatype is the 

Smart Station device type, and osver is the Smart Station system version, 

mgatype is listed as follows. 

LSJZX1K : Smart Station / Smart Station Pro 

LSSSMINIV1 : Smart Station Mini 

LSNAMIV1 : NatureMini 

LSNAMIV3 : NatureMiniPRO 

LSNAMIV4 : NatureMiniL 

LSMGANAV1 : NatureMiniS / Nature7 

LSHI3518 : Old version of Smart Station 

devname :if success the msg is success. 

upgrade : if success the msg is success. 

timezone : if success, the msg is whether the Smart Station is currently in 

daylight saving time, timezone is the current time zone of the Smart 

Station. 

return a non-zero error code indicating a request error. 21 

# 4. Local Event Service 

The LifeSmart Smart Station sends UDP messages to specific ports of devices to notify the local 

events, including the changes of device status, addition of sub-devices, deletion of sub-devices, 

and sub-devices' actions of going online and offline. For more information about event packet 

format, see 3.1 Message Format. The value of pkg_type is 9 (NOTIFY). 

To use local events, you need to set the notify command under SET-> config in section 3.3.10 to 

configure the IP address and port used by the third-party device to receive events. After the 

configuration is complete, notify configuration packets are sent every 300s. Otherwise, expiration 

occurs and events are not sent to the original IP address and port. 

The notify configuration is continuously maintained. When the status of the sub-device changes, an 

event is sent to the configured IP address and port. Multiple IP addresses and ports can be 

configured. 

# 4.1 Event Attribute Description 

Attribute 

Name Parameters Parameter Meaning Attribute Meaning 

id Event ID 

agtid Unique ID of the 

Smart Station 

chg 

devtype Device type, used to indicate the type of 

the device whose status is changed. 

Parameters 

related to the 

status change 

me Sub-device ID, used to indicate the ID of 

the device whose status is changed. 

name 

Device name, used to indicate that the 

name of the device has changed to this 

value. 

stat 

Device connection status (1: online, 0: 

offline), used to indicate that the device 

connection status has changed to this 

value. 

O/M/L1/L2/L3, 

etc. 

Device-specific attributes. For more 

information about the meaning and value 

of these parameters, see 6. Sub-devices. 

add 

devtype Device model 

Parameters 

related to newly 

added devices 

me Sub-device ID. Parameters obtained by 

Get eps. 

name Device name 

stat Device connection status (1: online, 0: 22 

offline) 

del 

devtype Device model Parameters 

related to deleted 

devices 

me Sub-device ID. Parameters obtained by 

Get eps. 

# 5. Scenes 

OpenDev interfaces support scene query and triggering. Every member of the scene list (array) 

returned by the scene query request contains the attribute values described in the query attribute 

description. The specific parameters required for different types of scene triggering are described 

in the scene triggering attributes. The specific scene number is required for scene triggering, which 

can be obtained by requesting the scene list. 

# 5.1 Scene Query Attribute Description 

Attribute 

Name Attribute Value Attribute Meaning 

id The value is a string that starts with 

an AI character. 

Obtain the scene number in the Smart 

Station (it is the same as the id parameter 

in scene triggering control requests). 

name Scene name set by the LifeSmart app Obtain the scene name in the Smart 

Station. 

desc Scene description set by the 

LifeSmart app 

Obtain the scene description in the Smart 

Station. 

cls 

Includes "scene", "groupirc", 

"groupsw", "grouphw", and 

"grouprgbw". 

Obtain the scene type in the Smart Station. 

# 5.2 Scene Triggering Attributes 

Type (cls) Name Parameter Control 

Parameter 

Control Parameter 

Value 

Scene Type 

Description 

scene Scene 

mode N/A N/A N/A Execute a scene 

mode. 

groupirc 

One-button 

infrared 

emission 

N/A N/A N/A 

Execute the 

configured one-

button infrared 

emission scene. 

groupsw One-button 

switching args type 0x81: On 

0x80: Off 

Turn on or off a

group of 

switches/bulbs. 

grouphw Extreme 

speed light args type 0x81: On 

0x80: Off 

Set a group of light 

bulbs. Broadcast 23 

group 0xff: set the color 

and turn on the 

light. 

0xfe: set the color 

and turn off the 

light. 

messages are used 

for turning on or off. 

The response is 

faster. 

RGBW 

4byte: WRGB. For 

more details, see 

RGBW IO 

description in 6.5.1 

Light Strip and 

Bulb. 

grouprgbw Light group args 

type 

0x81: On 

0x80: Off 

0xff: set the color 

and turn on the 

light. 

0xfe: set the color 

and turn off the 

light. 

Turn on or off a

group of 

switches/bulbs. 

RGBW 

4byte: WRGB. For 

more details, see 

RGBW IO 

description in 6.5.1 

Light Strip and 

Bulb. 

# 6. Sub-device 

In addition to common attributes, each type of the device has specific attribute values. For more 

information, see section 5.2. 

# 6.1 Common Attributes of Sub-devices 

Attribute 

Name Attribute Value Attribute Meaning 

devtype Sub-device type, which distinguishes 

device types. 

fulltype The complete parameter for the subdevice 

type, which is a complement to devtype 

name Sub-device name set in the Smart Station 24 

agt Device ID of the Smart Station to which the 

sub-device belongs 

me 2-byte hexadecimal string ("271f") Sub-device ID in the Smart Station 

stat 0: offline 

1: online Sub-device connection status 

lDbm The value is number ，in the unit of 

db m

RF signal strength in transmission direction 

from sub device to smart station 

epver The value is a string, the format is 

d.d.d.d sub-devices version 

data The value is in JSON format. It is the 

device-specific attributes. Device-specific attributes 

valts The value is a number in the unit of 

millisecond (ms). 

Time when the specific attribute changes. It 

is used for specific attributes. 

# 6.2 Attributes Specific to Sockets 

# 6.2.1 Traditional Sockets 

Devtype/Cls IO idx IO 

Name 

Read Attribute Value 

Description RW Control Command 

Description 

SL_OL_3C 

SL_OL_DE 

SL_OL_UK 

SL_OL_UL 

OD_WE_OT1 

O Switch v==1, on 

v==0, off RW 

To turn on the socket, 

deliver the following 

command: 

type=0x81, val=1; 

To turn off the socket, 

deliver the following 

command: 

type=0x80, val=0; 

# 6.2.2 Metering Socket 

Devtype/Cls IO idx IO Name Read Attribute 

Value Description RW Control Command 

Description 

SL_OE_W 

SL_OE_3C 

SL_OE_DE 

O Switch v==1, on 

v==0, off RW 

To turn on the socket, 

deliver the following 

command: 

type=0x81, val=1; 

To turn off the socket, 

deliver the following 25 

command: 

type=0x80, val=0; 

EE Electricity 

amount 

v indicates the 

cumulative power 

consumption, and 

the value is a

floating point 

number in kwh. 

R

EP Power 

Current load power. 

The value is a

floating point 

number and the unit 

is W. 

R

# 6.3 Attributes Specific to Switches 

# 6.3.1 Traditional Switch 

Devtype/Cls IO idx IO 

Name 

Read Attribute Value 

Description RW Control Command 

Description 

SL_SF_RC 

SL_SW_RC 

SL_SW_IF3 

SL_SF_IF3 

SL_SW_CP3 

SL_SW_RC3 

L1,L2,L3 Switch 

v==1, on 

v==0, off 

L1 indicates the first-

way switch. 

L2 indicates the 

second-way switch. 

L3 indicates the 

third-way switch. 

RW 

To turn on the socket, 

deliver the following 

command: 

type=0x81, val=1; 

To turn off the socket, 

deliver the following 

command: 

type=0x80, val=0; 

SL_SW_IF2 

SL_SF_IF2 

SL_SW_CP2 

SL_SW_FE2 

SL_SW_RC2 

L1,L2 Switch 

v==1, on 

v==0, off 

L1 indicates the first-

way switch. 

L2 indicates the 

second-way switch. 

RW 

To turn on the socket, 

deliver the following 

command: 

type=0x81, val=1; 

To turn off the socket, 

deliver the following 

command: 

type=0x80, val=0; 

SL_SW_IF1 

SL_SF_IF1 

SL_SW_CP1 

SL_SW_FE1 

SL_SW_RC1 

L1 Switch 

v==1, on 

v==0, off 

L1 indicates the first-

way switch. 

RW 

To turn on, deliver the 

following command: 

type=0x81, val=1; 

To turn off, deliver the 

following command: 26 

type=0x80, val=0; 

# 6.3.2 Stellar Switch/Sterry Switch/Polar Switch 

Devtype/Cls IO idx IO Name Read Attribute Value 

Description RW Control Command 

Description 

SL_SW_ND3 

L1,L2,L3 Switch 

v==1, on ;

v==0, off ;

L1 indicates the first-

way switch. 

L2 indicates the 

second-way switch. 

L3 indicates the third-

way switch. 

RW 

To turn on, 

command as follows: 

type=0x81, val=1; 

To turn off,command as 

follows: 

type=0x80, val=0; 

V

Electricit 

y

amount 

v is the battery level. 

Range (0-100) Units 

(%) R

SL_SW_ND2 

L1,L2 Switch 

v==1, on ;

v==0, off ;

L1 indicates the first-

way switch. 

L2 indicates the 

second-way switch. 

RW 

To turn on, 

command as follows: 

type=0x81, val=1; 

To turn off,command as 

follows: 

type=0x80, val=0; 

V

Electricit 

y

amount 

v is the battery level. 

Ran 

ge 

(0-

100) 

Unit 

s

(%) 

R

SL_SW_ND1 L1 Switch 

v==1, on ;

v==0, off ;

L1 indicates the first-

way switch. 

RW 

To turn on, 

command as follows: 

type=0x81, val=1; 

To turn off,command as 

follows: 

type=0x80, val=0; 27 

V

Electricit 

y

amount 

v is the battery level. 

Range (0-100) Units 

(%) 

R

# 6.3.3 Polar Switch (LN) 

Devtype/Cls IO idx IO Name Read Attribute 

Value Description RW Control Command 

Description 

SL_SW_BS3 L1,L2,L3 Switch 

v==1, on 

v==0, off 

L1 indicates the 

first-way switch. 

L2 indicates the 

second-way switch. 

L3 indicates the 

third-way switch. 

RW 

To turn on the switch, 

command as follows: 

type=0x81, val=1; 

To turn off the switch, 

command as follows: 

type=0x80, val=0; 

SL_SW_BS2 L1,L2 Switch 

v==1, on 

v==0, off 

L1 indicates the 

first-way switch. 

L2 indicates the 

second-way switch. 

RW 

To turn on the switch, 

command as follows: 

type=0x81, val=1; 

To turn off the switch, 

command as follows: 

type=0x80, val=0; 

SL_SW_BS1 L1 Switch 

v==1, on 

v==0, off 

L1 indicates the 

first-way switch. 

RW 

To turn on the switch, 

command as follows: 

type=0x81, val=1; 

To turn off the switch, 

command as follows: 

type=0x80, val=0 

# 6.3.4 Moonstone Switch 

Devtype/Cls IO idx IO Name Read Attribute 

Value Description RW Control Command 

Description 

SL_SW_NS3 L1,L2,L3 Switch 

v==1, on 

v==0, off 

L1 indicates the 

first-way switch. 

L2 indicates the 

second-way switch. 

L3 indicates the 

third-way switch. 

RW 

To turn on , deliver the 

following command: 

type=0x81, val=1; 

To turn off, deliver the 

following command: 

type=0x80, val=0; 28 

SL_SW_NS 2 L1,L2 Switch 

v==1, on 

v==0, off 

L1 indicates the 

first-way switch. 

L2 indicates the 

second-way switch. 

RW 

To turn on, deliver the 

following command: 

type=0x81, val=1; 

To turn off, deliver the 

following command: 

type=0x80, val=0; 

SL_SW_NS 1 L1 Switch 

v==1, on 

v==0, off 

L1 indicates the 

first-way switch. 

RW 

To turn on, deliver the 

following command: 

type=0x81, val=1; 

To turn off, deliver the 

following command: 

type=0x80, val=0; 

# 6.3.5 Stellar Switch/Sterry Switch/Polar Multi-control Accessory 

Devtype/Cls IO idx IO Name Read Attribute 

Value Description RW Control Command 

Description 

SL_MC_ND3 

L1,L2,L3 Switch 

v==1, on 

v==0, off 

L1 indicates the 

first-way switch. 

L2 indicates the 

second-way switch. 

L3 indicates the 

third-way switch. 

RW 

To turn on, deliver the 

following command: 

type=0x81, val=1; 

To turn off, deliver the 

following command: 

type=0x80, val=0; 

V Electricity 

amount 

v indicates the 

battery power. The 

range is (0-100) in 

the unit of %. 

R

B1,B2,B3 Button 

v==1, press 

v==0, release 

B1 indicates the first 

button. 

B2 indicates the 

second button. 

R29 

B3 indicates the 

third button. 

SL_MC_ND2 

L1,L2 Switch 

v==1, on 

v==0, off 

L1 indicates the 

first-way switch. 

L2 indicates the 

second-way switch. 

RW 

To turn on, deliver the 

following command: 

type=0x81, val=1; 

To turn off, deliver the 

following command: 

type=0x80, val=0; 

V Electricity 

amount 

v indicates the 

battery power. The 

range is (0-100) in 

the unit of %. 

R

B1,B2 Button 

v==1, press 

v==0, release 

B1 indicates the first 

button. 

B2 indicates the 

second button. 

R

SL_MC_ND1 

L1 Switch 

v==1, on 

v==0, off 

L1 indicates the 

first-way switch. 

RW 

To turn on, deliver the 

following command: 

type=0x81, val=1; 

To turn off, deliver the 

following command: 

type=0x80, val=0; 

V Electricity 

amount 

v indicates the 

battery power. The 

range is (0-100) in 

the unit of %. 

R

B1 Button 

v==1, press 

v==0, release 

B1 indicates the first 

button. 

R

# 6.3.6 CUBE Clicker(old version) 

Devtype/Cls IO idx IO Name Read Attribute Value 

Description RW Control Command 

Description 

SL_SC_BB B Button v==1, press 

v==0, release R

V Electricity v indicates the R30 

amount battery capacity. 

The range is (0-100) 

in the unit of %. 

# 6.3.7 CUBE Clicker (new version) 

Devtype/Cls IO idx IO Name Read Attribute Value 

Description RW Control Command 

Description 

SL_SC_BB_V2 

BN Button 

event 

v==1, press 

v==2, double-press 

v==255, press and 

hold 

R

V Electricity 

amount 

v indicates the 

battery power. The 

range is (0-100) in 

the unit of %. 

R

# 6.3.8 CUBE Switch Module 

Devtype/Cls IO idx IO 

Name 

Read Attribute Value 

Description RW Control Command 

Description 

SL_SW_MJ2 L1,L2 Switch 

v==1, on 

v==0, off 

L1 indicates the first-

way switch. 

L2 indicates the 

second-way switch. 

RW 

To turn on the switch, 

deliver the following 

command: 

type=0x81, val=1; 

To turn off the socket, 

deliver the following 

command: 

type=0x80, val=0; 

SL_SW_MJ1 L1 Switch 

v==1, on 

v==0, off 

L1 indicates the first-

way switch. 

RW 

To turn on the switch, 

deliver the following 

command: 

type=0x81, val=1; 

To turn off the socket, 

deliver the following 

command: 

type=0x80, val=0; 

# 6.3.9 Nature Mini/Nature Mini S/Nature Mini L/Nature Mini Pro (as 

# switch) 

Devtype/Cls IO idx IO 

Name 

Read Attribute Value 

Description RW Control Command 

Description 

SL_NATURE L1,L2,L3 Switch v==1, on RW To turn on, deliver the 31 

v==0, off 

L1 indicates the first-

way switch. 

L2 indicates the 

second-way switch. 

L3 indicates the 

third-way switch. 

following command: 

type=0x81, val=1; 

To turn off, deliver the 

following command: 

type=0x80, val=0; 

# 6.3.10 Smart Remote Controller 

Devtype/Cls IO idx IO 

Name 

Read Attribute Value 

Description RW Control Command 

Description 

SL_R_B 

eB1 Button 

event v==1, press R

eB2 Button 

event v==1, press R

eB3 Button 

event v==1, press R

eB4 Button 

event v==1, press R

eB5 Button 

event v==1, press R

eB6 Button 

event v==1, press R

eB7 Button 

event v==1, press R

eB8 Button 

event v==1, press R

V

Electricit 

y

amount 

v indicates the 

battery power. The 

range is (0-100) in 

the unit of %. 

R

# 6.4 Attributes Specific to Curtain Controllers 

# 6.4.1 Curtain Control Switch 

Devtype/Cls IO idx IO Name Read Attribute Value 

Description RW Control Command 

Description 

SL_SW_WIN 

SL_CN_IF 

SL_CN_FE 

OP 

Open the 

curtain 

(open) 

v==1, open the 

curtain RW 

To turn on the switch, 

deliver the following 

command: 

type=0x81, val=1; 32 

To turn off the socket, 

deliver the following 

command: 

type=0x80, val=0; 

ST 

Stop the 

curtain 

(stop) 

v==1, stop the 

curtain RW 

To turn on the switch, 

deliver the following 

command: 

type=0x81, val=1; 

To turn off the socket, 

deliver the following 

command: 

type=0x80, val=0; 

ST 

Close the 

curtain 

(close) 

v==1, close the 

curtain RW 

To turn on the switch, 

deliver the following 

command: 

type=0x81, val=1; 

To turn off the socket, 

deliver the following 

command: 

type=0x80, val=0; 

# 6.4.2 DOOYA Curtain Motor 

Devtype/Cls IO idx IO Name Read Attribute Value 

Description RW Control Command 

Description 

SL_DOOYA P1 Curtain 

state 

Type%2==1, The 

control is underway. 

Type%2==0, The 

control is not 

underway. 

When the control is 

underway (that is, 

type%2==1), 

Val&0x80==0x80 

indicates that the 

curtain is being 

opened. Otherwise, it 

is being closed. 

The value of 

val&0x7F indicates 

R33 

the percentage of 

curtain opening 

([0,100]). 

If the value of 

val&0x7F is greater 

than 100, the curtain 

opening state cannot 

be obtained. It can 

be obtained only 

after the curtain is 

fully opened or 

closed. 

P2 Curtain 

control 

Delivered 

percentage of curtain 

opening 

RW 

To fully open the curtain, 

deliver the following 

command: 

type=0xCF, val=100; 

To fully close the curtain, 

deliver the following 

command: 

type=0xCF, val=0; 

To stop the curtain, deliver 

the following command: 

type=0xCE, val=0x80; 

To open the curtain to a

specific percentage, 

deliver the following 

command: 

Type=0xCF, val=percent; 

percentage value: [0,100]; 

# 6.4.3 MINS Curtain Motor Controller 

The devtype of the MINS curtain motor controller is SL_P. The specific attributes are the 

same as those of the general controller. However, only three attributes P2, P2, and P4 are 

used for curtain control. The attribute P8 indicates the power capacity. For details, see 

6.9.1 General Controller .

# 6.5 Attributes Specific to Lighting Devices 

# 6.5.1 Light Strip and Bulb 34 

Devtype/Cls IO idx IO 

Name 

Read Attribute 

Value Description RW Control Command 

Description 

SL_CT_RGBW 

SL_LI_RGBW 

RGBW 

RGBW 

color 

value 

Type%2==1, on 

Type%2==0, off 

The value of val is a

color value and is 4

bytes in size. It is 

defined as follows: 

bit0~bit7: Blue 

bit8~bit15: Green 

bit16~bit23: Red 

bit24~bit31: White 

For example: 

Red: 0x00FF0000 

White: 0xFF000000 

RW 

Turn on the light: 

type=0x81, val=1; 

Turn off the light: 

type=0x80, val=0; 

Turn on the light and set 

the color value: 

Type=0xff, val=color 

value; 

Turn off the light and set 

the color value: 

Type=0xfe, val=color 

value; 

Note: If the action is "turn 

off", the light device will be 

turned off. If the action is 

"turn on", you need to 

refer to the DYN 

configuration. If DYN is 

enabled, the DYN 

configuration has a higher 

priority than the RGBW 

configuration. If you only 

want to display the color, 

please disable DYN. You 

can set the DYN and 

RGBW values together by 

calling the SET eps 

interface commands. 

DYN 

Dynamic 

color 

value 

Type%2==1, enable 

dynamic color 

Type%2==0, disable 

dynamic color 

val indicates the 

dynamic color value. 

For specific dynamic 

color values, see 

RW 

Enable: type=0x81, val=1; 

Disable: type=0x80, val=0; 

Enable and set dynamic 

color values: 

Type=0xff, val=dynamic 

color value; 

Disable and set dynamic 

color values: type=0xfe, 35 

Appendix 7.2 

Dynamic Color (DYN) 

Definition. 

val=dynamic color value; 

Note: Currently, DYN 

configurations cannot be 

delivered separately and 

must be delivered with 

RGBW configurations. 

Please use the EpsSet 

interface commands to set 

the DYN and RGBW 

values together. If the 

current light is turned off, 

you need to enable 

RGBW, that is RGBW 

type=0x81; val=1. Then 

set DYN to specific 

values. 

SL_SC_RGB RGB 

RGB 

color 

value 

Type%2==1, on 

RW 

Turn on the light: 

type=0x81, val=1; 

Type%2==0, off 

The value of val is a

color value and is 4

bytes in size. It is 

defined as follows: 

bit0~bit7:Blue 

Turn off the light: 

type=0x80, val=0; 

Turn on the light and set 

the color or enable 

dynamic color: 

bit8~bit15: Green 

bit16~bit23:Red 

Type=0xff, val=color or 

dynamic value; 

bit24~bit31:White 

(When White> =128, 

dynamic mode is 

used) For more 

information about 

specific dynamic 

values, see Appendix 

7.2 Dynamic Color 

(DYN) Definition. 

Turn off the light and set 

the color or enable 

dynamic color: type=0xfe, 

val=color or dynamic 

value; 

# 6.5.2 SPOT 

Devtype/Cls IO idx IO 

Name 

Read Attribute Value 

Description RW Control Command 

Description 36 

MSL_IRCTL 

RGBW 

RGBW 

color 

value 

Type%2==1, on 

Type%2==0, off 

The value of val is a

color value and is 4

bytes in size. It is 

defined as follows: 

bit0~bit7: Blue 

bit8~bit15: Green 

bit16~bit23: Red 

bit24~bit31: White 

For example: 

Red: 0x00FF0000 

White: 0xFF000000 

RW 

Turn on the light: 

type=0x81, val=1; 

Turn off the light: 

type=0x80, val=0; 

Turn on the light and set 

the color value: 

Type=0xff, val=color 

value; 

Turn off the light and set 

the color value: 

Type=0xfe, val=color 

value; 

Note: If the action is "turn 

off", the light device will 

be turned off. If the action 

is "turn on", you need to 

refer to the DYN 

configuration. If DYN is 

enabled, the DYN 

configuration has a

higher priority than the 

RGBW configuration. If 

you only want to display 

the color, please disable 

DYN. You can set the 

DYN and RGBW values 

together by calling the 

SET eps interface 

commands. 

DYN 

Dynamic 

color 

value 

Type%2==1, enable 

dynamic color 

Type%2==0, off 

Dynamic 

val indicates the 

dynamic color value. 

For specific dynamic 

color values, see 

Appendix 7.2 

RW 

Enable: type=0x81, 

val=1; 

Disable: type=0x80, 

val=0; 

Enable and set dynamic 

color values: 

Type=0xff, val=dynamic 

color value; 

Disable and set dynamic 37 

Dynamic Color (DYN) 

Definition. 

color values: type=0xfe, 

val=dynamic color value; 

Note: Currently, DYN 

configurations cannot be 

delivered separately and 

must be delivered with 

RGBW configurations. 

Please use the EpsSet 

interface commands to 

set the DYN and RGBW 

values together. If the 

current light is turned off, 

you need to enable 

RGBW, that is RGBW 

type=0x81; val=1. Then 

set DYN to specific 

values. 

OD_WE_IRCTL RGB 

RGB 

color 

value 

Type%2==1, on 

Type%2==0, off 

The value of val is a

color value and is 

4 bytes in size. It is 

defined as follows: 

bit0~bit7: Blue 

bit8~bit15: Green 

bit16~bit23: Red 

bit24~bit31: White 

(When White> =128, 

the dynamic mode is 

used) For more 

information about 

specific dynamic 

values, see Appendix 

7.2 Dynamic Color 

(DYN) Definition. 

RW 

Turn on the light: 

type=0x81, val=1; 

Turn off the light: 

type=0x80, val=0; 

Turn on the light and set 

the color or enable 

dynamic color: 

Type=0xff, val=color or 

dynamic value; 

Turn off the light and set 

the color or enable 

dynamic color: type=0xfe, 

val=color or dynamic 

value; 

SL_SPOT RGB 

RGB 

color 

value 

Type%2==1, on 

Type%2==0, off 

The value of val is a

RW 

Turn on the light: 

type=0x81, val=1; 

Turn off the light: 38 

color value and is 4

bytes in size. It is 

defined as follows: 

bit0~bit7: Blue 

bit8~bit15: Green 

bit16~bit23: Red 

bit24~bit31: White 

(When White>=128, 

dynamic mode is 

used) For more 

information about 

specific dynamic 

values, see Appendix 

7.2 Dynamic Color 

(DYN) Definition. 

type=0x80, val=0; 

Turn on the light and set 

the color or enable 

dynamic color: 

Type=0xff, val=color or 

dynamic value; 

Turn off the light and set 

the color or enable 

dynamic color: type=0xfe, 

val=color or dynamic 

value; 

SL_P_IR P2 

Pairing 

button 

status 

For the 922 RF 

version of the Spot 

(mini), fulltype=sl_ P_ 

IR_ V2, P2 is used to 

indicate the pairing 

button status. 

type%2==1,indicates 

the pairing button is 

pressed; 

type%2==0,indicates 

the pairing button is 

released; 

Note: 

P2 only indicates the 

pairing button is 

pressed, 

not indicates whether 

it is currently in the 

pairing state 

P2 for the 433 RF 

Spot(mini), 

R39 

fulltype=sl_ P_ IR_ 

V1 does not exist. 

# 6.5.3 Lights Series 

Devtype/Cls IO 

idx IO Name Description of Attribute 

value RW Description of Issued 

Command 

SL_LI_GD1 

L Brightnes 

s value 

type%2==1 ,turn on ;

type%2==0 ,turn off ;

val value is the 

brightness value whose 

size is 1 byte with a

range of [0~255] .

0 is 0% brightness ，

255 is 100% brightness. 

RW 

turn on : type=0x81, val=1; 

turn off : type=0x80, val=0; 

turn on and set the 

brightness: 

type=207, val= brightness 

value ;

turn off and set the 

brightness ：

type=206, val= brightness 

value ;

M Motion 

detection 

v==1, 

motion detected ;

v==0, 

No motion detected ;

R

Z

Illuminati 

on 

intensity 

v value means 

Illumination intensity 

with unit(lux) 

R

SL_SPWM L Brightnes 

s value type%2==1 , turn on; 

type 

%2= 

=0 ,t 

urn 

off ;

SL_SW_DM1 L Brightnes 

s value 

type%2==1 , turn on; 

type%2==0 ,turn off ;

val value is the 

brightness value whose 

size is 1 byte with a

range of [0~255] .

0 is 0% brightness ，

255 is 100% brightness. 

RW 

turn on : type=0x81, val=1; 

turn off : type=0x80, val=0; 

turn on and set the 

brightness: 

type=207, val= brightness 

value ;

turn off and set the 

brightness ：

type=206, val= brightness 

value ;40 

I Indicator 

type%2==1 ,turn on ;

type%2==0 ,turn off ;

The val is the 

brightness level whose 

size is 2 byte,defined as 

follows: 

bit0~bit7: 

brightness of indicators 

when the light is off,with 

the range of [0~255] 

bit8~bit15: 

brightness of indicators 

when the light is 

on ,withe the range of 

[0~255] 

RW 

To turn on the 

indicator,command as 

follows :

type=0x81, val=1; 

To turn off the 

indicator,command as 

follows :

type=0x80, val=0; 

Enable and set the 

brightness value when the 

light is on and the 

brightness value when the 

light is off: 

type=223, 

val= the brightness value 

when the light is on | the 

brightness value when the 

light is off. 

Turn off and set the 

brightness value when the 

light is on and the 

brightness value when the 

light is off: 

type=222, 

val= the brightness value 

when the light is on | the 

brightness value when the 

light is off. 

M Motion 

detection 

v==1, 

move detected ;

v==0 ,

no movement detected; 

R

Z

Illuminati 

on 

intensity 

v value means 

Illumination intensity 

with unit(lux) 

R

SL_LI_WW 

P1 Brightnes 

s value 

type%2==1 , turn on; 

type%2==0 ,turn off ;

val value is the 

brightness value whose 

size is 1 byte with a

range of [0~255] .

0 is 0% brightness ，

255 is 100% brightness. 

RW 

turn on : type=0x81, val=1; 

turn off : type=0x80, val=0; 

turn on and set the 

brightness: 

type=207, val= brightness 

value ;

turn off and set the 

brightness ：

type=206, val= brightness 

value ;

P2 

Color 

temperat 

ure 

control 

val value is the color 

temperature value 

whose value range is 

[0,255].0 means warm 

light, 255 means cool 

RW 

To set the color 

tempertur,command as 

follows: 

type=207, val= color 

temperature value ,41 

light; color temperature 

value =[0,255] 

# 6.6 Attributes Specific to Sensors 

# 6.6.1 Door Sensors 

Devtype/Cls IO idx IO Name Read Attribute Value 

Description RW Control Command 

Description 

SL_SC_G 

G Door state v==1, closed 

v==0, open R

V Electricity 

amount 

v indicates the 

battery power. The 

range is (0-100) in 

the unit of %. 

R

SL_SC_BG 

G Door state v==1, closed 

v==0, open R

V Electricity 

amount 

v indicates the 

battery power. The 

range is (0-100) in 

the unit of %. 

R

B Button v==1, press 

v==0, release R

AXS Vibration 

state 

v==0 indicates no 

vibration. Non-zero 

values of v indicates 

vibration. 

R

# 6.6.2 Dynamic Sensor 

Devtype/Cls IO idx IO Name Read Attribute Value 

Description RW Control Command 

Description 

SL_SC_MHW M Movement 

detection 

v==1, 

indicates that 

movement is 

detected. 

v==0, 

indicates that no 

movement has been 

R42 

detected. 

V Electricity 

amount 

v indicates the 

battery capacity. The 

range is (0-100) in 

the unit of %. 

R

SL_SC_BM 

SL_SC_CM 

M Movement 

detection 

v==1, 

indicates that 

movement is 

detected. 

v==0, 

indicates that no 

movement has been 

detected. 

R

Z Illuminance 

The value of v

represents the 

illuminance in lux. 

R

V Electricity 

amount 

v indicates the 

battery capacity. The 

range is (0-100) in 

the unit of %. 

R

# 6.6.3 Environmental Sensor 

Devtype/Cls IO idx IO Name Read Attribute Value 

Description RW Control Command 

Description 

SL_SC_THL 

SL_SC_BE 

T

Ambient 

temperatur 

e

The value of v

represents the 

temperature in °C. 

R

H Ambient 

humidity 

The value of v

represents the 

humidity in %. 

R

Z Illuminance 

The value of v

represents the 

illuminance in lux. 

R

V Electricity 

amount 

v indicates the 

battery capacity. The 

range is (0-100) in 

the unit of %. 

R

# 6.6.4 Water Leak Sensor 43 

Devtype/Cls IO idx IO Name Read Attribute 

Value Description RW Control Command 

Description 

SL_SC_WA 

WA Conductivity 

v==0, 

indicates that no 

water is detected. 

v > 0, 

A larger value 

indicates more 

water and a higher 

conductivity. 

R

V Electricity 

amount 

v indicates the 

battery capacity. 

The range is (0-100) 

in the unit of %. 

R

# 6.6.5 Gas Sensor (Formaldehyde) 

Devtype/Cls IO idx IO Name Read Attribute 

Value Description RW Control Command 

Description 

SL_SC_CH 

CH2O 

Formaldehyd 

e

concentration 

The value of v

represents the 

current 

formaldehyde 

concentration in the 

unit of mg/m3. 

The safe 

formaldehyde 

concentration range 

is [0,0.086] mg/m3. 

R

O Alarm status 1: Alarming 

0: Normal R

V Electricity 

amount 

v indicates the 

battery capacity. 

The range is (0-

100) in the unit 

of %. 

R

# 6.6.6 Gas Sensor (Gas) 

Devtype/Cls IO idx IO Name Read Attribute 

Value Description RW Control Command 

Description 44 

SL_SC_CP 

ANALOG 

Gas 

concentratio 

n

The value of v

represents the 

current gas 

concentration. 

R

O Alarm status 1: Alarming 

0: Normal R

V Electricity 

amount 

v indicates the 

battery capacity. 

The range is (0-

100) in the unit 

of %. 

R

# 6.6.7 Environmental Sensor (TVOC+CO2) 

Devtype/Cls IO idx IO Name Read Attribute Value 

Description RW Control Command 

Description 

SL_SC_CQ 

T Ambient 

temperature 

The value of v

represents the 

temperature in °C. 

R

H Ambient 

humidity 

The value of v

represents the 

humidity in %. 

R

CO2 

CO2 

concentratio 

n

The value of v

represents the CO2 

concentration in the 

unit of ppm. 

The following ranges 

are defined for 

reference. 

val <= 500: excellent 

val <= 700: good 

val <= 1000: medium 

val > 1000: poor 

R

TVOC 

TVOC 

concentratio 

n

The value of v

represents the TVOC 

concentration in the 

unit of mg/m ³.

The following ranges 

are defined for 

R45 

reference. 

val < 0.34: excellent 

val < 0.68: good 

val <= 1.02: medium 

val > 1.02: poor 

V Electricity 

amount 

v indicates the 

battery capacity. The 

range is (0-100) in 

the unit of %. 

R

# 6.6.8 Smoke Sensor 

Devtype/Cls IO idx IO Name Read Attribute Value 

Description RW Control Command 

Description 

SL_P_A 

P1 

Is there 

an 

alarm? 

v==1, indicates that there 

is a smoke alarm. 

v==0, indicates that there 

is no smoke alarm. 

R

P2 Voltage 

val indicates the voltage 

value in the unit of V. If a

9 V battery is used, the 

actual voltage value is 

(val/100)*3. Note that its 

value may exceed 9 V, 

for example, 9.58 V. 

This value is invalid if an 

external 12 V power 

supply is used. 

R

# 6.6. 9 Environmental Sensor (CO2) 

Devtype/Cls IO idx IO Name Read Attribute Value 

Description RW Control Command 

Description 

SL_SC_CA 

T

Ambient 

temperat 

ure 

The value of v represents 

the temperature in °C. R

H

Ambient 

humidity 

The value of v represents 

the humidity in %. R

CO2 CO2 The value of v represents R46 

concentr 

ation 

the CO2 concentration in 

the unit of ppm. 

The following ranges are 

defined for reference. 

val <= 500: excellent 

val <= 700: good 

val <= 1000: medium 

val > 1000: poor 

V

Electricit 

y amount 

v indicates the battery 

capacity. The range is (0-

100) in the unit of %. 

R

# 6.7 Attributes Specific to Smart Door Locks 

# 6.7.1 Smart Door Locks 

Devtype/Cls IO idx IO Name Read Attribute Value 

Description RW Control Command 

Description 

BAT Electricity 

amount 

v indicates the battery 

capacity. The range is (0-

100) in the unit of %. 

R

ALM Alarm 

information 

The values of val are 

defined as follows: 

bit0: 1 indicates an error 

alarm (an alarm is 

generated if you try the 

wrong password or 

fingerprint or card more than 

10 times). 

bit1: 1 indicates the 

kidnapping alarm (an alarm 

is generated if you use the 

anti-kidnapping password or 

anti-kidnapping fingerprint 

for unlocking). 

bit2: 1 indicates the anti-

smashing alarm (lock is 

picked). bit3: 1 indicates the 

mechanical key alarm (a 

R47 

mechanical key is used for 

unlocking). 

bit4: 1 indicates a low 

voltage alarm (low battery 

capacity). 

bit5: 1 indicates the alarm 

for abnormal actions. bit6: 1

indicates the doorbell. 

bit7: 1 indicates a fire alarm. 

bit8: 1 indicates the intrusion 

alarm. 

EVTOP Operation 

record 

The length of val is 8, 24, or 

32 bits. You can obtain the 

length based on the type. 

The method is as follows: 

Type=0x40+(8-1)*2 or 

type=0x40+(16-1)*2 or 

type=0x40+(32-1)*2 

The general encoding order 

for val is as follows: 

[1-byte record type] 

[2-byte user ID] 

[1-byte user flag] 

User flag: 

bit01=11 indicates the 

administrator. 

bit01=01 indicates a

common user. 

bit01=00 indicates that the 

user has been deleted. 

R

SL_LK_LS 

SL_LK_GTM 

SL_LK_AG 

SL_LK_SG 

SL_LK_YL 

EVTLO 

Real-time 

lock 

information 

Type%2==1, locked 

Type%2==0, unlocked 

The values of val are 

defined as follows: 

bits 0 to 11 indicate user ID. 

bits 12 to 15 indicate the 

unlocking method. 

0: not defined; 

R48 

1: password; 

2: fingerprint; 

3: NFC; 

4: mechanical key; 

5: remote unlocking; 

6: One-key unlocking 

(unlocking signals); 

7: Unlocking via app 

15: An error occurred. 

bits 16 to 27 indicate user 

ID. 

bits 28 to 31 indicate the 

unlocking method (as 

defined above). 

Note: Two methods may be 

used at the same time to 

open the door lock. In this 

case, bits 0 to 15 and bits 16 

to 31 indicate respective 

unlocking information. If one 

method is used, bits 0 to 15 

indicate the unlocking 

information and other bits 

are set to 0. 

HISLK 

Information 

about the 

last 

unlocking 

action 

Type%2==1, locked 

Type%2==0, unlocked 

The values of val are 

defined as follows: 

bits 0 to 11 indicate user ID. 

bits 12 to 15 indicate the 

unlocking method. 

0: not defined; 

1: password; 

2: fingerprint; 

3: NFC; 

4: mechanical key; 

5: remote unlocking; 

6: One-key unlocking 

R49 

(unlocking signals); 

7: Unlocking via app 

15: An error occurred. 

bits 16 to 27 indicate user 

ID. 

bits 28 to 31 indicate the 

unlocking method (as 

defined above). 

# 6.7. 2 C100/C200 doorlock 

Devtype/Cls IO idx IO Name Read Attribute Value 

Description RW Control Command 

Description 

BAT Electricity 

amount 

v indicates the battery 

capacity. The range is (0-

100) in the unit of %. 

R

ALM Alarm 

information 

The values of val are 

defined as follows: 

bit0: 1 indicates an error 

alarm (an alarm is 

generated if you try the 

wrong password or 

fingerprint or card more 

than 10 times). 

bit1: 1 indicates the 

kidnapping alarm (an alarm 

is generated if you use the 

anti-kidnapping password 

or anti-kidnapping 

fingerprint for unlocking). 

bit2: 1 indicates the anti-

smashing alarm (lock is 

picked). 

bit3: 1 indicates the 

mechanical key alarm (a 

mechanical key is used for 

unlocking). 

bit4: 1 indicates a low 

voltage alarm (low battery 

R50 

capacity). 

bit5: 1 indicates the alarm 

for abnormal actions. 

bit6: 1 indicates the 

doorbell. 

bit7: 1 indicates a fire 

alarm. 

bit8: 1 indicates the 

intrusion alarm. 

bit11: 1 indicates return 

to factory default alarm. 

EVEBE 

LL 

Bell 

information 

type%2=1 indicates that 

there is a doorbell 

message. 

type%2=0 indicates that 

there is nodoorbell 

message. 

R

EVTOP Operation 

record 

The length of val is 8, 24, or 

32 bits. You can obtain the 

length based on the type. 

The method is as follows: 

Type=0x40+(8-1)*2 or 

type=0x40+(16-1)*2 or 

type=0x40+(32-1)*2 

The general encoding order 

for val is as follows: 

[1-byte record type] 

[2-byte user ID] 

[1-byte user flag] 

User flag: 

bit01=11 indicates the 

administrator. 

bit01=01 indicates a

common user. 

bit01=00 indicates that the 

user has been deleted. 

R

SL_LK_LS 

SL_LK_GTM EVTLO Real-time 

lock 

Type%2==1, locked 

Type%2==0, unlocked R51 

SL_LK_AG 

SL_LK_SG 

SL_LK_YL 

information The values of val are 

defined as follows: 

bits 0 to 11 indicate user ID. 

bits 12 to 15 indicate the 

unlocking method. 

0: not defined; 

1: password; 

2: fingerprint; 

3: NFC; 

4: mechanical key; 

5: remote unlocking; 

6: One-key unlocking 

(unlocking signals); 

7: Unlocking via app 

15: An error occurred. 

bits 16 to 27 indicate user 

ID. 

bits 28 to 31 indicate the 

unlocking method (as 

defined above). 

Note: Two methods may be 

used at the same time to 

open the door lock. In this 

case, bits 0 to 15 and bits 

16 to 31 indicate respective 

unlocking information. If 

one method is used, bits 0

to 15 indicate the unlocking 

information and other bits 

are set to 0. 

HISLK 

Information 

about the 

last 

unlocking 

action 

Type%2==1, locked 

Type%2==0, unlocked 

The values of val are 

defined as follows: 

bits 0 to 11 indicate user ID. 

bits 12 to 15 indicate the 

unlocking method. 

0: not defined; 

R52 

1: password; 

2: fingerprint; 

3: NFC; 

4: mechanical key; 

5: remote unlocking; 

6: One-key unlocking 

(unlocking signals); 

7: Unlocking via app 

15: An error occurred. 

bits 16 to 27 indicate user 

ID. 

bits 28 to 31 indicate the 

unlocking method (as 

defined above). 

# 6.8 Attributes Specific to Temperature Controllers 

# 6.8.1 HVAC Controller 

Devtype/Cls IO idx IO Name Read Attribute Value 

Description RW Control Command 

Description 

SL_TR_XX P1 

Central air 

conditioning 

system 

information 

The low 24-bit value of 

val is used to distinguish 

the types of central air 

conditioning systems. 

Currently, two types are 

supported. 

val&0xffffff=0x000001; 

val&0xffffff=0x000002; 

Note: For central air 

conditioning systems, 

the control panels 

should be searched by 

using the cfg: airctrl 

commands. For details, 

see the description of 

cfg:airctrl commands in 

3.3.10. Configuration 

Commands of the Smart 

Station. 

R53 

# 6.8.2 Control Panel of HVAC Controller 

Devtype/Cls IO idx IO Name Read Attribute Value 

Description RW Control Command 

Description 

V_AIR_P 

ALM Alarm 

status 

v> 1, indicates an 

alarm. 

v==0, off; 

R

O Switch v==1, open; 

v==0, off; RW 

To turn on the switch, 

deliver the following 

command: 

type=0x81, val=1; 

To turn off the socket, 

deliver the following 

command: 

type=0x80, val=0; 

MODE Mode 

v indicates the 

modes, which are 

defined as follows: 

1: Auto 

2: Fan 

3: Cooling 

4: Heating 

5: Dehumidification 

RW 

In the command, type is 

0xCE. The definition of 

values of val is the same 

as the attribute value 

description. 

F Wind 

speed 

v represents the wind 

speeds, which are 

defined as follows: 

val<30: low 

val<65: medium 

Val> =65: high 

RW 

In the command, type is 

0xCE. The values of val 

are as follows: 

Low, val=15; 

Medium, val=45; 

High, val=75; 

tT 

Target 

temperatur 

e

The value of v

represents the 

temperature in °C. 

RW 

In the command, type is 

0x88. val needs to be set 

to the original temperature 

value, that is, the target 

temperature value*10. 

For example, if the set 

temperature is 25 ℃,

val=250 should be 

delivered. 

T Current The value of v R54 

temperatur 

e

represents the 

temperature in °C. 

# 6.8.3 Underfloor Thermostat 

Devtype/Cls IO idx IO Name Read Attribute Value 

Description RW Control Command 

Description 

SL_CP_DN 

P1 System 

configuration 

For details about the 

type and val fields of 

this IO, see Table 6-

8-3. 

RW 

To turn on the socket, 

deliver the following 

command: 

type=0x81, val=1; 

To turn off the socket, 

deliver the following 

command: 

type=0x80, val=0; 

If you need to modify the 

configuration of val, 

remain the current value 

of type unchanged and 

set val to the target value. 

P2 Valve switch v==1, on; 

v==0, off; R

P3 Target 

temperature 

The value of v

represents the 

temperature value in 

the unit of °C. 

RW 

In the command, type is 

0x88. val needs to be set 

to the original 

temperature value, that is, 

the target temperature 

value*10. 

For example, if the set 

temperature is 25 ℃,

val=250 should be 

delivered. 

P4 Indoor 

temperature 

The value of v

represents the 

temperature value in 

the unit of °C. 

R

P5 Floor 

temperature 

The value of v

represents the 

temperature value in 

the unit of °C. 

R55 

TYPE 

Explan 

ation 

The lowest bit indicates the running state of the system. 

0:OFF 1:ON 

Bit 

Num 

ber 

31 24~19 18~17 

16 

~1 

5

14~1 

1 10~8 7~3 2 1 0

VAL 

Explan 

ation 

Setti 

ng 

Mode 

: 0: 

manu 

al 

mode 

1: 

auto 

matic 

mode 

Tempe 

rature 

limit =

val +

40 

Tempe 

rature 

control 

mode 

Tim 

e

peri 

od 

Exter 

nal 

probe 

differ 

ence 

=

(val-

10)/5 

Intern 

al 

probe 

differ 

ence 

=

(val-

10)/5 

Tempe 

rature 

correcti 

on =

val/2 +

5

Anti-

free 

zing 

Po 

wer 

stat 

us 

afte 

r

po 

wer 

fail 

ure 

Backl 

ight 

Table 6-8-3 

# 6.8.4 Fan Coil Thermostat 

Devtype/Cls IO idx IO Name Read Attribute Value 

Description RW Control Command 

Description 

SL_CP_AIR 

P1 System 

configuration 

For details about the 

type and val fields of 

this IO, see Table 6-

8-4. 

RW 

To turn on the switch, 

deliver the following 

command: 

type=0x81, val=1; 

To turn off the socket, 

deliver the following 

command: 

type=0x80, val=0; 

If you need to modify the 

configuration of val, 

remain the current value 

of type unchanged and 

set val to the target value. 

P2 Valve switch v==1, on; 

v==0, off; R

P4 Target The value of v RW In the command, type is 56 

temperature represents the 

temperature value in 

the unit of °C. 

0x88. val needs to be set 

to the original 

temperature value, that is, 

the target temperature 

value*10. 

For example, if the set 

temperature is 25 ℃,

val=250 should be 

delivered. 

P5 Indoor 

temperature 

The value of v

represents the 

temperature value in 

the unit of °C. 

R

TYPE 

Explanation 

The lowest bit indicates the running state of the system. 

0:OFF 1:ON 

VAL 

Explanation 

Bit 

Numbe 

r

16~15 14~13 12~8 7~3 2 1 0

Setting 

Wind 

speed: 

0: 

automati 

c; 

1~3: 1~3 

levels; 

Mode: 

0: cooling; 

1: 

heating; 

2: 

ventilation 

;

Dt0 

external 

probe 

differenc 

e = val/2 

Temperatur 

e

correction 

= val/2 + 5

sat 

State 

after 

powe 

r

failur 

e

Backligh 

t

Fa 

n

Fn 

Table 6-8-4 

# 6.8.5 Air Conditioner Control Panel 

Devtype/Cls IO idx IO Name Read Attribute Value 

Description RW Control Command 

Description 

SL_UACCB 

ALM Alarm 

status 

v>1, indicates an 

alarm. 

v==0, off; 

R

O Switch v==1, on; 

v==0, off; RW 

To turn on the socket, 

deliver the following 

command: 

type=0x81, val=1; 

To turn off the socket, 57 

deliver the following 

command: 

type=0x80, val=0; 

MODE Mode 

v indicates the 

modes, which are 

defined as follows: 

1: Auto 

2: Fan 

3: Cooling 

4: Heating 

5: Dehumidification 

RW 

In the command, type is 

0xCE. The definition of 

values of val is the same 

as the attribute value 

description. 

F Wind 

speed 

v represents the wind 

speeds, which are 

defined as follows: 

val<30: low 

val<65: medium 

Val>=65: high 

RW 

In the command, type is 

0xCE. The values of val 

are as follows: 

Low, val=15; 

Medium, val=45; 

High, val=75; 

tT 

Target 

temperatur 

e

The value of v

represents the 

temperature value in 

the unit of °C. 

RW 

In the command, type is 

0x88. val needs to be set 

to the original temperature 

value, that is, the target 

temperature value*10. 

For example, if the set 

temperature is 25 ℃,

val=250 should be 

delivered. 

T

Current 

temperatur 

e

The value of v

represents the 

temperature value in 

the unit of °C. 

R

# 6.8.6 Nature Mini Pro(Thermostat) 

Devtype/Cls IO idx IO Name Read Attribute Value 

Description RW Control Command 

Description 

SL_NATUR 

E L1 Switch v==1, on; 

v==0, off; RW 

To turn on , deliver the 

following command: 

type=0x81, val=1; 

To turn off , deliver the 

following command: 58 

type=0x80, val=0; 

L2 Valve1 

v==1, open; 

v==0, off; 

Note: the valve status 

is used to indicate the 

actual working status 

of the current 

equipment. The valve 

is mainly connected 

to the hot and cold 

valve of the coil 

R

L3 Valve2 

v==1, open; 

v==0, off; 

Note: the valve status 

is used to indicate the 

actual working status 

of the current 

equipment. The valve 

is mainly connected 

to the hot valve of the 

value or floor heating 

valve. 

R

T

Current 

temperatur 

e

The value of v

represents the 

temperature value in 

the unit of °C. 

R

P5 Device 

type 

Val indicates the 

device type, 

The format is 

0xAABB, 

AA :useless, 

BB :equipment type, 

BB=1, switch; 

BB=2 Poe panel; 

Bb=3,temperature 

control panel; 

Note: 

If there is no P5 

R59 

attribute, it is also a

switch 

P6 

HVAC 

configuratio 

n

For details about the 

type and val fields of 

this IO, refer to Table 

6-8-6. 

RW 

If you need to modify the 

configuration of Val, :

Type :keeps the current 

value; 

Val : equal to the value to 

be configured; 

P7 Mode 

Type=0xCE, fixed; 

val indicates the 

modes, which are 

defined as follows: 

1: Auto 

2: Fan 

3: Cool 

4: Heat 

5: Dry 

7:Warm 

8:Warm+Heat 

RW 

command as follows: 

type=0xce, 

The Val value definition is 

the same as the attribute 

value description. 

P8 

Target 

temperatur 

e

Type=0x88, fixed; 

Val:the original 

temperature value, 

which is an integer of 

temperature value 

*10. Temperature 

unit: ℃

RW 

When issuing the 

command, type=0x88, 

Val needs to use the 

original temperature 

value, i.e. the target 

temperature value *10. 

For example, if the setting 

temperature is 25 ℃,

val=250 should be issued 

P9 Target 

wind speed 

type=0xCE;fixed 

val is wind speed 

which defined as 

follows: 

val=0:stop 

val<30: low 

val<65: medium 

Val>=65: high 

val>100:auto 

RW 

When issuing the 

command, type=0xce, 

val are as follows 

stop:val=0 

low:val=15 

medium:val=45 

high:val=75 

auto:val=105 60 

P10 Current 

wind speed 

val is wind speed 

which defined as 

follows: 

val=0:stop 

val<30: low 

val<65: medium 

Val>=65: high 

val>100:auto 

R

TYPE 

Explan 

ation 

Fixed 0xFE 

Bit 11~9 8~6 5~0 

VAL 

Explan 

ation 

Setting 

contents 

Temperature 

return difference, 

(v+1) *0.25 as 

temperature 

return difference 

parameter 

HVAC settings: 

0: fresh air; 

1: Fan coil unit (single 

valve) mode; 

2: Water heating mode; 

3: Fan coil + water 

heating; 

4: Fan coil double valve; 

5: Ground heating +

fresh air; 

Temperature correction, 

6-digit signed integer, 

range 

[-8,+8] 

Table 6-8-6 

# 6.8.7 Nature Thermostat 

Devtype/Cls IO idx IO Name Read Attribute Value 

Description RW Control Command 

Description 

SL_FCU 

O Switch v==1, open; 

v==0, off; RW 

To turn on,deliver the 

following command: 

type=0x81, val=1; 

To turn off,deliver the 

following command: 

type=0x80, val=0; 

VALVE 

1 Valve1 

v==1, open; 

v==0, off; 

Note: the valve status 

is used to indicate the 

R61 

actual working status 

of the current 

equipment. The valve 

is mainly connected 

to the hot and cold 

valve of the coil 

VALVE 

2 Valve2 

v==1, open; 

v==0, off; 

Note: the valve status 

is used to indicate the 

actual working status 

of the current 

equipment. The valve 

is mainly connected 

to the hot valve of the 

coil or floor heating 

valve. 

R

T

Current 

temperatur 

e

The value of v

represents the 

temperature value in 

the unit of °C. 

R

P5 Device 

type 

Val indicates the 

equipment type, 

The format is 

0xAABB, 

AA useless, 

BB equipment type, 

Bb=3,temperature 

control panel; 

R

P6 

HVAC 

configuratio 

n

For details about the 

type and val fields of 

this IO, see Table 6-

8-6. 

RW 

If you need to modify the 

configuration of Val, issue: 

Type keeps the current 

value; Val is equal to the 

value to be configured; 

P7 Mode 

Type=0xCE, fixed; 

val indicates the 

modes, which are 

RW 

When issuing the 

command, type=0xce, 62 

defined as follows: 

1: Auto 

2: Fan 

3: Cool 

4: Heat 

5: Dry 

7:Warm 

8:Warm+Heat 

The Val value definition is 

the same as the attribute 

value description. 

P8 

Target 

temperatur 

e

Type=0x88, fixed; 

Val refers to the 

original temperature 

value, which is an 

integer of temperature 

value *10. 

Temperature unit: ℃

RW 

When issuing the 

command, type=0x88, 

Val needs to use the 

original temperature 

value, i.e. the target 

temperature value *10. 

For example, if the setting 

temperature is 25 ℃,

val=250 should be issued 

P9 Target 

wind speed 

type=0xCE;fixed 

val is wind 

speed;which defined 

as follows: 

val=0:stop 

val<30: low 

val<65: medium 

Val>=65: high 

val>100:auto 

RW 

When issuing the 

command, type=0xCE, 

val are as follows 

stop:val=0 

low:val=15 

medium:val=45 

high:val=75 

auto:val=105 

P10 Current 

wind speed 

val is wind 

speed;which are 

defined as follows: 

val=0:stop 

val<30: low 

val<65: medium 

Val>=65: high 

val>100:auto 

R

TYPE 

Explan Fixed 0xFE 63 

ation 

Bit 11~9 8~6 5~0 

VAL 

Explan 

ation 

Setting 

contents 

Temperature 

return difference, 

(v+1) *0.25 as 

temperature 

return difference 

parameter 

HVAC settings: 

0: fresh air; 

1: Fan coil unit (single 

valve) mode; 

2: Water heating mode; 

3: Fan coil + water 

heating; 

4: Fan coil double valve; 

5: Ground heating +

fresh air; 

Temperature correction, 

6-digit signed integer, 

range 

[-8,+8] 

Table 6-8-6 

# 6.8.8 Thermostatic Radiator Valve 

Devtype/Cls IO idx IO Name Read Attribute Value 

Description RW Control Command 

Description 

SL_CP_VL 

P1 

System 

configuratio 

n

For details about the 

type and val fields of 

this IO, see Table 6-8-

4. 

RW 

To turn on the switch, 

deliver the following 

command: 

type=0x81, val=1; 

To turn off the socket, 

deliver the following 

command: 

type=0x80, val=0; 

If you need to modify the 

configuration of val, remain 

the current value of type 

unchanged and set val to 

the target value. 

P2 Valve 

switch 

v==1, on; 

v==0, off; R64 

tT 

Target 

temperatur 

e

The value of v

represents the 

temperature value in 

the unit of °C. 

RW 

In the command, type is 

0x88. val needs to be set 

to the original temperature 

value, that is, the target 

temperature value*10. 

For example, if the set 

temperature is 25 ℃,

val=250 should be 

delivered. 

T

Current 

temperatur 

e

The value of v

represents the 

temperature value in 

the unit of °C. 

R

ALM Alarm 

status 

Val indicates alarm 

information: 

Bit0: high 

temperature 

protection 

Bit1: low 

temperature 

protection 

bit2:int_ sensor 

bit3:ext_ sensor 

Bit4: Low battery 

Bit5: The device is 

offline 

R

V

Electricity 

amount 

v indicates the battery 

capacity. The range is 

(0-100) in the unit 

of %. 

R 

> TYPE
> Explanatio
> n

least significant digit indicates the system startup status 65 

0:OFF 1:ON 

> VAL
> Explanatio
> n

BIT 2~1 0

Setting contents 

A value of 0 indicates manual mode; 

A value of 1 indicates energy saving 

mode; 

A value of 2 indicates automatic mode; 

A value of 0 indicates 

that the child lock is 

disabled. A value of 1

indicates that the child 

lock is enabled .

# 6.8.9 HVAC Smart Controlle r- ventilation 

Devtype/Cls IO idx IO Name Read Attribute Value 

Description RW Control Command 

Description 

V_FRESH_P 

O Switch 

v==1, on; 

v==0, off; 

RW 

To turn on the socket, 

deliver the following 

command: 

type=0x81, val=1; 

To turn off the socket, 

deliver the following 

command: 

type=0x80, val=0; 

O1 Switch 

v==1, on; 

v==0, off; 

RW 

To turn on the socket, 

deliver the following 

command: 

type=0x81, val=1; 

To turn off the socket, 

deliver the following 

command: 66 

type=0x80, val=0; 

MODE Mode 

v is the mode. See 

Note 2 for 

definitions of each 

version .

RW 

type=0xCE when the 

command is sent, 

val value setting mode, 

see Note 2 for version 

control; 

F Wing 

speed 

v is wind speed, 

which is defined as 

follows: 

v<0: stops. 

v<30: low; 

v<65: medium; 

v>=65: high grade; 

RW 

type=0xCE when the 

command is sent, 

val values are as 

follows: 

Stop, val=0; 

Low, val=15; 

Middle, val=45; 

High grade, val=75; 

Where ver=8, 9, 16, 31 

Device does not 

support stop (val=0) 

F1 blower 

v is wind speed, 

which is defined as 

follows: 

v<0: stops. 

v<30: low; 

v<65: medium; 

v>=65: high grade; 

RW 

type=0xCE when the 

command is sent, 

val values are as 

follows: 

Stop, val=0; 

Low, val=15; 

Middle, val=45; 

High grade, val=75; 67 

F2 Exhaust 

fan 

v is wind speed, 

which is defined as 

follows: 

v<0: stops. 

v<30: low; 

v<65: medium; 

v>=65: high grade; 

RW 

type=0xCE when the 

command is sent, 

val values are as 

follows: 

Stop, val=0; 

Low, val=15; 

Middle, val=45; 

High grade, val=75; 

H Ambient 

humidity 

The value of v

represents the 

humidity in %. 

R

T

Current 

temperatu 

re 

The value of v

represents the 

temperature value 

in the unit of °C. 

R

T2 Temperat 

ure 2

The v value is the 

temperature value, 

v > 100 indicates 

an error, 

Unit: ℃

R

Note1 ：Not all of the preceding IO idx all exist in the panels. Different versions of fresh air 

panels correspond to different external computers, so different IO idx and V_FRESH_P 

versions exist. You can see the ver attribute of the device. 

Note2 ：Different models correspond to different versions of fresh air panels. The value of 

MODE means different meanings. For the device version, see the ver attribute 

•ver=3: 

Bits 0-1:0x01: manual, 0x10: timed 

2-3 bits: 0x01: Heat exchange, 0x10: Frost proof 

•ver=8: 

v=1: automatic; v=2: blow air; v=9: sleep; v=10: time period; 

•ver=9, 14, 31: none MODE; 68 

•ver=16: 

v=1: automatic; v=6: purification; v=12: internal cycle; v=13: outer cycle .

# 6.9 Attributes Specific to General Controller 

# 6.9.1 General Controller 

Devtype/C 

ls 

IO 

idx IO Name Read Attribute Value 

Description RW Control Command 

Description 

SL_P 

P1 Configuratio 

n

See the note in this 

section. RW See the note in this 

section. 

P2 Control port 

1

type%2==1, on 

Type%2==0, off 

RW 

To turn on the socket, 

deliver the following 

command: 

type=0x81, val=1; 

To turn off the socket, 

deliver the following 

command: 

type=0x80, val=0; 

P3 Control port 

2

type%2==1, on 

Type%2==0, off 

RW 

To turn on the switch, 

deliver the following 

command: 

type=0x81, val=1; 

To turn off the socket, 

deliver the following 

command: 

type=0x80, val=0; 

P4 Control port 

3

type%2==1, on 

Type%2==0, off 

RW 

To turn on the switch, 

deliver the following 

command: 

type=0x81, val=1; 

To turn off the socket, 

deliver the following 

command: 69 

type=0x80, val=0; 

P5 State port 1

Type%2==1 indicates 

state triggering. It is 

valid only in free mode. 

R

P6 State port 2

Type%2==1 indicates 

state triggering. It is 

valid only in free mode. 

R

P7 State port 3

Type%2==1 indicates 

state triggering. It is 

valid only in free mode. 

R

P8 Electricity 

amount 

v indicates the battery 

capacity. The range is 

(0-100) in the unit %. It 

is applicable only to 

the MINS curtain motor 

controller. 

R

Note: 

• The working modes of P2, P3, and P4 are determined by P1. The val value of P1 is a

32-bit integer, which is described as follows: bit 31 value: 1 indicates software setting. 

0 indicates the working mode is set by the hardware itself. (val > > 24) & 0xe 

0: free mode 

2: two-wire curtain 

4: three-wire curtain 

6: DC motor 

8: three-way switch 

10: three-way switch (rocker) 

Jogging and holding: (val > > 24) & 1

0: holding, for example, switch 

1: Jogging. Move when the button is pressed. Stop when the button is released. 

When modifying the value of P1, you need to keep data of unmodified bits unchanged. 70 

• If the working mode is two-wire curtain, three-wire curtain, or DC motor: 

P2 means to open the curtain. P3 means to close the curtain. P4 means to stop the 

curtain. 

For details, see 6.4.1 Curtain Control Switch. 

• If the working mode is three-way switch or three-way switch (rocker): 

P2 indicates the first-way switch. P3 indicates the second-way switch. P4 indicates the 

third-way switch. 

For details, see 6.3.1 Traditional Switch. 

• If the working mode is free mode, P5, P6, and P7 indicate the status. 

They can be connected to the different relay output dry contacts of the sensor device 

with wired output (such as smoke sensor, gas sensor, infrared fence, flame sensor, etc.). 

When detecting signals, P5, P6 and P7 will react accordingly. 

# 6.9.2 485 Controller 

Devtype/Cls IO idx IO Name Read Attribute Value 

Description RW Control Command 

Description 

V_485_P P1 Value 

the value of the 

current access 

device. ‘val ’ is in 

terms of IEEE 754 

standard float 32-bit 

integer, ‘v’ is a float 

number with the unit 

is the current unit of 

the specific access 

device. 

For example, if the 

access device is a

pressure sensor, then 

val is the current 

pressure value of the 

access device, in the 

units set by the 

access device. 

RW 

Caution: ‘val ’ is in 

terms of IEEE 754 

standard float 32-bit 

integer. 

Example:102491364 

3 presents a float 

number 0.03685085, 

the integer number 

could be calculated 

by the float number. 

More details: IO float 

type instruction 

# 6.9.3 DLT Smart Plug 

Devtype/Cls IO idx IO Name Read Attribute Value 

Description RW Control Command 

Description 71 

V_DLT_645 

_P 

EE 

Electricit 

y

consump 

ti 

on 

v==1, indicates that no 

sound is playing. 

v==0, indicates that 

sounds are playing. 

R

Caution: ‘val ’ is in 

terms of IEEE 754 

standard float 32-bit 

integer. 

Example:102491364 

3 presents a float 

number 0.03685085, 

the integer number 

could be calculated 

by the float number. 

More details: IO float 

EP Power 

Current load power, 

‘val ’ is in terms of 

IEEE 754 standard 

float 32-bit integer, 

‘v’ is a float number 

with w. 

R

Caution: ‘val ’ is in 

terms of IEEE 754 

standard float 32-bit 

integer. 

Example:102491364 

3 presents a float 

number 0.03685085, 

the integer number 

could be calculated 

by the float number. 

More details: IO float 

type instruction 

# 6.9. 4 HA Interface Adapter （JEMA) 

Devtype/Cls IO idx IO 

Name 

Description of 

Attribute Value 

R

W

Description of Issued 

Command 

SL_JEMA P1 

confugu 

ration 

Refer to Note RW Refer to Note 

P2 Ctrl1 type%2==1 indicates 

turn-on; type%2==0 

indicates turn-off; 

RW To turn on the general 

controller, issue: 

type=0x81; val=1; 

To disable, issue: 

type=0x80; val=0; 

P3 Ctrl2 type%2==1 indicates 

turn-on; type%2==0 

indicates turn-off; 

RW To turn on the general 

controller, issue: 

type=0x81; val=1; 

To disable, issue: 

type=0x80; val=0; 72 

P4 Ctrl3 type%2==1 indicates 

turn-on; type%2==0 

indicates turn-off; 

RW To turn on the general 

controller, issue: 

type=0x81; val=1; 

To disable, issue: 

type=0x80; val=0; 

P5 Status1 type%2==1 indicates 

state triggering. It is 

valid only in free 

mode. 

R

P6 Status2 type%2==1 indicates 

state triggering. It is 

valid only in free 

mode. 

R

P7 Status3 type%2==1 indicates 

state triggering. It is 

valid only in free 

mode. 

R

P8 HA1 type%2==1 indicates 

turn-on; type%2==0 

indicates turn-off; 

RW To turn on the general 

controller, issue: 

type=0x81; val=1; 

To disable, issue: 

type=0x80; val=0; 

P9 HA2 type%2==1 indicates 

turn-on; type%2==0 

indicates turn-off; 

RW To turn on the general 

controller, issue: 

type=0x81; val=1; 

To disable, issue: 

type=0x80; val=0; 

P10 HA3 type%2==1 indicates 

turn-on; type%2==0 

indicates turn-off; 

RW To turn on the general 

controller, issue: 

type=0x81; val=1; 

To disable, issue: 

type=0x80; val=0; 

Note: 

• The working modes of P2, P3, and P4 are determined by P1. 

P1.val (an integer of 32-bit) .The gener al controller (HA), whose value is always 1, is a read-only property .

(1 indicates setting by the software; 0 indicates setting by the hardware) 

• Working mode: (val >>> 24) & 0xe 

0. free mode 

2. two-wire curtain 

4. three-wire curtain 

6. DC motor 

8. three-way switch 

10. three-way switch (rocker) 

• Inching and holding: (val >>> 24) & 1

0: Holding, for example, switch 

1.Inching: connect when the button is pressed; disconnect when the button is released. 

• How many seconds of delay after opening before the function configuration closed automatically ：val &

0x7FFFF 

18bit: 3rd way 1: enable, 0 disable 

17bit: 2nd way 1:enable, 0 disable 

16bit: 1st way 1: enable, 0 disable 

15-0bit: Delay in seconds, Highs at the front, lows at the back 

Affected by working mode (some working modes only use 2 wires, then only 2 wires will work) 73 

• When modifying the P1 value, you need to keep data of unmodified bits unchanged. 

• If the working mode is two-wire curtain, three-wire curtain, or DC motor: 

P2 means to open the curtain; P3 means to close the curtain; P4 means to stop the curtain. 

For specific meaning, please refer to 6.4.1Curtain Controller. 

• If the working mode is three-way switch or three-way switch (rocker): 

P2 indicates the first-way switch; P3 indicates the second-way switch; P4 indicates the third-way switch. 

For specific meaning, please refer to 6.3.1 Switch Series .

• If the working mode is free mode, P5, P6, and P7 indicate the state. 

They can be connected to different relay output dry contacts of sensor devices with wired output (such as 

smoke sensor, gas sensor, infrared fence, flame sensor, etc.). When detecting signals, P5, P6 and P7 will 

reflect state accordingly. 

• P8, P9 and P10 are the switch interfaces of HA (Home Automation), which are independent and will not be 

affected by P1. For concrete commands, see description of the above table. 

# 6.9. 5 Status Indicator 

Devtype/Cls IO 

idx 

IO Name Read Attribute 

Value Description 

RW Control Command Description 

V_IND_S L1 …L

20 

Switch 1…

Switch20 

v==lindicates on; 

v==0indicates off 

RW 

Turning it on, deliver the following 

command: 

type=0x81,val=1; 

Turning it off, deliver the following 

command: type=0x80,val=0; 

# 6.9. 6 Eliq Electricity meter 

Devtype/Cls IO idx IO Read Attribute Value RW Control Command 74 

Name Description Description 

ELIQ_EM 

EPA power 

V is the current load 

power, the value is a

floating number, and 

the unit is w. 

R

V Battery V is battery percentage, 

range(0-100) unit(%) R

# 6.10 Attributes Specific to Smart Station MINI 

# 6.10.1 Built-in Alarm of the Smart Station MINI 

Devtype/Cls IO idx IO Name Read Attribute Value 

Description RW Control Command 

Description 

LSSSMINIV1 P1 Alarming 

status 

v==1, indicates that no 

sound is playing. 

v==0, indicates that 

sounds are playing. 

RW 

To stop playing sounds, 

deliver the following: 

type=0x80; 

To set the playback 

sound, deliver the 

following: 

type=0x81, mandatory 

val=int type, alarm sound 

ID, range (1-4, 

expandable to 7), 

mandatory 

loop=int type, the number 

of times the alarm sound 

is played, less than 20, 

optional 

vol=int type, volume, 

effective volume (60-100), 

optional 

clear=bool type, whether 

to clear the sound being 

played, optional 75 

# 6.11 Defed Series 

# 6.11.1 Defed PIR Sensor 

Devtype/Cls IO idx IO Name Read Attribute Value 

Description RW Control Command 

Description 

SL_DF_MM 

M Motion 

Detection 

v==1, 

indicates motion 

v==0, 

indicates no motion 

R

T Temperatu 

re 

V indicates 

temperature, 

Unit: ℃

R

TR Tamper 

Alarm 

v==1, 

indicates tampered 

v==0, 

indicates no tamper 

R

V Battery V is battery percentage, 

range(0-100) unit(%) R

# 6.11.2 Defed Door/window sensor 

Devtype/Cls IO idx IO Name Read Attribute Value 

Description RW Control Command 

Description 

SL_DF_GG 

A

Door/wind 

ow 

sensor 

v==1, indicates open 

v==0, indicates closed R

A2 Alarm v==1, indicates alarm 

v==0, indicates no alarm R

T Temperat 

ure 

V indicates temperature, 

Unit: ℃ R

TR Tamper 

Alarm 

v==1, 

indicates tampered 

v==0, 

indicates no tamper 

R

V Battery V is battery percentage, 

range(0-100) unit(%) R76 

# 6.11.3 Defed Keyfob 

Devtype/Cls IO idx IO Name Read Attribute Value 

Description RW Control Command 

Description 

SL_DF_BB 

eB1 Button v==1, indicates click R

eB2 Button v==1, indicates click R

eB3 Button v==1, indicates click R

eB4 Button v==1, indicates click R

V Battery V is battery percentage, 

range(0-100) unit(%) R

# 6.11.4 Defed Indoor Siren 

Devtype/Cls IO idx IO Name Read Attribute Value 

Description RW Control Command 

Description 

SL_DF_SR 

P1 Siren 

control 

Send command to set 

the siren go off RW 

Set play sound, issue: 

type=0xff, required 

val=int type, 

Parameters: 

dura(duration) 0-30 s

vol(volume) 0-255 

id(Sound id) 0，1(warning 

sound) ，2(alarm sound) 

nval = ((dura * 10) << 8) |

vol 

val = (nval << 8) | id 

SR Alarm v==1, indicates alarm 

v==0, indicates normal R

T Temperat 

ure 

V indicates temperature, 

Unit: ℃ R77 

TR Tamper 

Alarm 

v==1, 

indicates tampered 

v==0, 

indicates no tamper 

R

V Battery V is battery percentage, 

range(0-100) unit(%) R

# 7. Appendix 

# 7.1 Smart Devices 

Devtype/Cls Name 

Sockets 

SL_OL_3C Smart socket 

SL_OL_DE Socket complying with German standards 

SL_OL_UK Socket complying with British standards 

SL_OL_UL Socket complying with American standards 

OD_WE_OT1 Wi-Fi socket 

SL_OL_W In-wall socket 

SL_OE_3C Metering socket 

SL_OE_DE Metering socket with German standards 

Switch 

SL_SW_IF1 BLEND light switch - one key 

SL_SW_IF2 BLEND light switch - two keys 

SL_SW_IF3 BLEND light switch - three keys 

SL_SF_IF1 BLEND light switch with live line - one key 

SL_SF_IF2 BLEND light switch with live line - two keys 

SL_SF_IF3 BLEND light switch with live line - three keys 

SL_SW_CP1 Orange BLEND light switch - one key 

SL_SW_CP2 Orange BLEND light switch - two keys 

SL_SW_CP3 Orange BLEND light switch - three keys 

SL_SW_FE1 Senna/Gezhi switch - one key 

SL_SW_FE2 Senna/Gezhi switch - two keys 

SL_SW_RC Three-way touchable switch 78 

SL_SF_RC Three-way one-live-line touchable switch 

SL_SW_RC1 120 Smart light switch - one key 

SL_SW_RC2 120 Smart light switch - two keys 

SL_SW_RC3 120 Smart light switch - three keys 

SL_SW_ND1 Stellar switch - one key 

SL_SW_ND2 Stellar switch - two keys 

SL_SW_ND3 Stellar switch - three keys 

SL_MC_ND1 Stellar switch partner - one key 

SL_MC_ND2 Stellar switch partner - two keys 

SL_MC_ND3 Stellar switch partner - three keys 

SL_SW_BS3 Polar Switch (LN) - three keys 

SL_SW_BS2 Polar Switch (LN) - two keys 

SL_SW_BS1 Polar Switch (LN)- one key 

SL_SW_NS3 Moonstone Switch - three keys 

SL_SW_NS2 Moonstone Switch - two keys 

SL_SW_NS1 Moonstone Switch - one key 

SL_SC_BB CUBE Clicker 

SL_SC_BB_V2 Free button 

SL_SW_MJ1 CUBE switch module - one key 

SL_SW_MJ2 CUBE switch module - two keys 

SL_NATURE Nature Mini/Nature Mini S/Nature Mini L/Nature Mini Pro 

SL_R_B Smart Remote Controller 

Curtain controllers 

SL_CN_IF BLEND curtain controller 

SL_CN_FE Gezhi/Senna three-key curtain controller 

SL_SW_WIN Curtain controller 

SL_DOOYA Curtain (DuYa) 

SL_P_V2 MINS curtain motor controller 

Lighting 

SL_LI_RGBW Capsule bulb 

SL_CT_RGBW BLEND light strip 

SL_SC_RGB BLEND light strip (without white light) 

SPOT 

MSL_IRCTL SPOT (basic edition, Bluetooth edition) 

OD_WE_IRCTL SPOT (quick connection) 

SL_SPOT SPOT (CoSS) 

SL_P_IR 922 RF version of the SPOT (mini) 79 

Sensors 

SL_SC_G Door sensor 

SL_SC_BG CUBE door sensor 

SL_SC_MHW Dynamic sensor 

SL_SC_CM Dynamic sensor (AAA battery) 

SL_SC_BM CUBE dynamic sensor 

SL_SC_THL Environmental sensor 

SL_SC_BE CUBE environmental sensor 

SL_SC_CQ Environmental sensor (CO2+TVOC) 

SL_SC_WA Water leak sensor 

SL_SC_CH Gas sensor (formaldehyde) 

SL_SC_CP Gas sensor (gas) 

SL_P_A Smoke sensor 

SL_SC_CA Environmental sensor (CO2) 

Defed Series 

SL_DF_MM Defed PIR Sensor 

SL_DF_GG Defed Door/window sensor 

SL_DF_BB Defed Keyfob 

SL_DF_SR Defed Indoor Siren 

Temperature controller 

SL_TR_XX HVAC controller 

V_AIR_P Control panel of HVAC controller 

SL_CP_DN Underfloor thermostat 

SL_CP_AIR Fan coil thermostat 

SL_UACCB Air conditioner control panel 

SL_NATURE Nature Mini Pro(Thermostat) 

SL_FCU Nature Thermostat 

SL_CP_VL Thermostatic Radiator Valve 

V_FRESH_P HVAC Smart Controlle r- ventilation 

Door locks 

SL_LK_LS Smart door lock 

SL_LK_GTM Smart door lock (Yale door lock) 

SL_LK_AG Smart door lock (Schlage lock module) 

SL_LK_SG Singea smart door lock 

SL_LK_YL Yale/Gateman door lock module 

Others 

SL_P General controller 80 

V_485_P 485 controller 

V_DLT_645 _P DLT Smart Plug 

LSSSMINIV1 Multi-function alarm 

V_IND_S Status Indicator 

ELIQ_EM Eliq Electricity meter 

# 7.2 Dynamic Color (DYN) Definition 

Effect Value of val 

Grass 0x8218cc80 

Sea wave 0x8318cc80 

Dark blue mountains 0x8418cc80 

Flirtatious purple 0x8518cc80 

Raspberry 0x8618cc80 

Orange 0x8718cc80 

Autumn fruit 0x8818cc80 

Ice cream 0x8918cc80 

Plateau 0x8020cc80 

Pizza 0x8120cc80 

Fruit juice 0x8a20cc80 

Warm cottage 0x8b30cc80 

Magic red 0x9318cc80 

Light spot 0x9518cc80 

Blue 0x9718cc80 

First rays of the 

morning sun 0x9618cc80 

Hibiscus 0x9818cc80 

Colorful era 0x9918cc80 

Heaven 0xa318cc80 

Charm blue 0xa718cc80 

Bright red 0xa918cc80