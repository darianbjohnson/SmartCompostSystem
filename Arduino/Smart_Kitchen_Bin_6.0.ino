/*

Darian Johnson
part of the Smart Compost System
This code measures the amount of scraps in a kitchen scrap bin

*/

#include <CurieBLE.h>
#include <Average.h>

Average<float> ave(5);

boolean blinkState = false;          // state of the LED
unsigned long loopTime = 0;          // get the time since program started
unsigned long interruptsTime = 0;    // get the time when motion event is detected

int led = 13;
int ledClose = 10;
int switchReed = 6;
const long binInterval = 120000;

boolean wasOpen = false;

/********************************************************************/
//BLE settings

BLEPeripheral blePeripheral;  // BLE Peripheral Device (the board you're programming)
BLEService kitchenBinService("9a4587b1-4d85-4c75-b88b-faa619295a18"); // BLE Service
BLECharacteristic kitchenBinLevel("9a4587b2-4d85-4c75-b88b-faa619295a18", BLERead | BLENotify , 5);

/********************************************************************/
//Ultrasonic Settings
#define SIG A0
unsigned long rxTime;
float distance;

int binDepth = 19.5; //cm; this accounts for the lid and the ultrasoonic sensor

unsigned long previousMillis = 0;

void setup() {
  /********************************************************************/
  //Set up Reed Switch
  pinMode(switchReed, INPUT);
  Serial.begin(9600);
  Serial.println("Starting");

  /********************************************************************/
  //BLE setup
  blePeripheral.setLocalName("KitchenBin");
  blePeripheral.setAdvertisedServiceUuid(kitchenBinService.uuid());

  // add service
  blePeripheral.addAttribute(kitchenBinService);

  //add characteristics
  blePeripheral.addAttribute(kitchenBinLevel);

  //set initial values
  getLevel();

  blePeripheral.begin();

}
void loop() {

  //get amount in bin every 2 hours;
  unsigned long currentMillis = millis();
  if (currentMillis - previousMillis >= binInterval) {
    getLevel();
    previousMillis = currentMillis;
  }

}


int getLevel() {

  //int distanceArray[100];
  for (int x = 0; x < 5; x++) { //get average
    //set SIG as OUTPUT,start to output trigger signal to the module to start the ranging
    pinMode(SIG, OUTPUT);
    //Genarate a pulse 20uS pulse
    digitalWrite(SIG, HIGH);
    delayMicroseconds(20);
    digitalWrite(SIG, LOW);
    //set SIG as INPUT,start to read value from the module
    pinMode(SIG, INPUT);

    rxTime = pulseIn(SIG, HIGH);//waits for the pin SIG to go HIGH, starts timing, then waits for the pin to go LOW and stops timing

    distance = (float)rxTime  / 29 / 2;//convert the time to distance in CM

    delay(10);

    ave.push(round(distance));

  }

  distance = ave.mean();

  Serial.print("distance: "); //print distance:
  Serial.print(distance / 2.54); //print the distance
  Serial.println("In"); //and the unit

  int binFill = binDepth;

  //leave the distance between 2cm-800cm
  if (distance < 2)
  {
    distance = 0; //bin is full
  }

  if (distance > 19.5)
  {
    Serial.println("There was an error; use default value of  zero");
  }
  else {

    binFill = binDepth - distance;
  }


  char charArray[5];
  dtostrf(binFill, 5, 0, charArray);
  kitchenBinLevel.setValue(charArray);

  Serial.print("binFill: "); //print distance:
  Serial.print(binFill); //print the distance
  Serial.println("CM"); //and the unit


  return binFill;


}

