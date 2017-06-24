/*

Darian Johnson
part of the Smart Compost System
This code controls sensors in the compost and controls pumps and vents

*/



/********************************************************************/
// First we include the libraries
#include <Adafruit_Si7021.h>

#include <OneWire.h>
#include <DallasTemperature.h>
#include <Servo.h>
#include <Wire.h>
#include <CurieBLE.h>
#include <CurieTime.h>
//#include <Power.h>


/********************************************************************/
//BLE settings

BLEPeripheral blePeripheral;  // BLE Peripheral Device (the board you're programming)
BLEService compostService("0411dc90-895b-4639-b627-c663f6726c3c"); // BLE Servic

BLECharacteristic readingDateTime("0411dc91-895b-4639-b627-c663f6726c3c", BLERead | BLENotify | BLEWrite, 20);
BLECharacteristic compostTempF("0411dc92-895b-4639-b627-c663f6726c3c", BLERead , 5);
BLECharacteristic ambientTempF("0411dc93-895b-4639-b627-c663f6726c3c", BLERead, 5);
BLECharacteristic compostMoisture("0411dc94-895b-4639-b627-c663f6726c3c", BLERead , 5 );
BLECharacteristic methanePPM("0411dc95-895b-4639-b627-c663f6726c3c", BLERead, 5);
BLECharacteristic waterLevel("0411dc96-895b-4639-b627-c663f6726c3c", BLERead, 2);
BLEUnsignedCharCharacteristic ventAngle("0411dc97-895b-4639-b627-c663f6726c3c", BLERead | BLEWrite);
BLEUnsignedCharCharacteristic startPump("0411dc98-895b-4639-b627-c663f6726c3c", BLERead | BLEWrite);

/********************************************************************/

/********************************************************************/
//Governing settings
int sleepMS = 30000; //300000;
int awakeSec = 10;
int waitforEdisonMS = 15000;

/********************************************************************/
//Ambient Temp Settings
Adafruit_Si7021 sensorAmbTemp = Adafruit_Si7021();

/********************************************************************/


/********************************************************************/
//Temperature settings
// Data wire is plugged into pin 2 on the Arduino
#define ONE_WIRE_BUS 2
// Setup a oneWire instance to communicate with any OneWire devices
// (not just Maxim/Dallas temperature ICs)
OneWire oneWire(ONE_WIRE_BUS);
// Pass our oneWire reference to Dallas Temperature.
DallasTemperature sensors(&oneWire);
/********************************************************************/

/********************************************************************/
//Moisture settings
int moistureSensorPin = A0;
/********************************************************************/

/********************************************************************/
//Methane settings
int methaneSensorPin = A1;
/********************************************************************/

/********************************************************************/
//Servo settings
int servoPin = 9;
Servo servo;
int action = 0;
/********************************************************************/


/********************************************************************/
//Water Pump Settings
int pumpPin = 8; // pin that turns on the motor
int pumpTimeToRun = 4000; //4 sec
/********************************************************************/

/********************************************************************/
//Water Float Settings
int waterLevelPin = 7; // pin that turns on the motor
/********************************************************************/


void setup() {
  // start serial port
  Serial.begin(115200);
  Serial.println("Starting Smart Compost System");

   pinMode(pumpPin, OUTPUT); //set pump pin as output

  /********************************************************************/
  // Start up the library
  sensorAmbTemp.begin();
  

      Serial.print("Humidity:    "); Serial.print(sensorAmbTemp.readHumidity(), 2);
  Serial.print("\tTemperature: "); Serial.println(sensorAmbTemp.readTemperature(), 2);
  int temperatureC = sensorAmbTemp.readTemperature();

  int temperatureF = (temperatureC * 9.0 / 5.0) + 32.0;

  Serial.print("\tTemperature F: "); Serial.println(temperatureF);
  delay(2000);


sensors.begin();

  


  /********************************************************************/
  //Initialize Servo
  servo.attach(servoPin);
  servo.write(action); //close the servo

  /********************************************************************/
  //BLE setup
  blePeripheral.setLocalName("Compost");
  blePeripheral.setAdvertisedServiceUuid(compostService.uuid());

  // add service
  blePeripheral.addAttribute(compostService);

  //add characteristics
  blePeripheral.addAttribute(readingDateTime);
  blePeripheral.addAttribute(compostTempF);
  blePeripheral.addAttribute(ambientTempF);
  blePeripheral.addAttribute(compostMoisture);
  blePeripheral.addAttribute(methanePPM);
  blePeripheral.addAttribute(waterLevel);
  blePeripheral.addAttribute(ventAngle);
  blePeripheral.addAttribute(startPump);



  //get Sensor Readings
  readSensors() ;

  ventAngle.setValue(0);
  startPump.setValue(0);

  blePeripheral.begin();

}

void loop() {

  BLECentral central = blePeripheral.central();
  if (central) {
    Serial.print("Connected to Edison: ");
    // print the central's MAC address:
    Serial.println(central.address());

    while (central.connected()) {

      readSensors();

      if (startPump.written()) {
        if (startPump.value()) {   // any value other than 0
          Serial.println("Start Pump");
          digitalWrite(pumpPin, HIGH);     //Switch Pump ON
          delay(pumpTimeToRun);            //Wait 10 Seconds
          digitalWrite(pumpPin, LOW);      //Switch Pump OFF
          startPump.setValue(0);
        } else {
          Serial.println("don't start pump");
        }
      }

      if (ventAngle.written()) {
        if (ventAngle.value()) {   // any value other than 0
          Serial.println("Open Vent");
          servo.write(180);
        } else {
          Serial.println("Close Vent");
          servo.write(0);
        }
      }
    }
    // when the central disconnects, print it out:
    Serial.print(F("Disconnected from Edison: "));
    Serial.println(central.address());
  }

  //PM.sleep(sleepMS);
  //PM.deepSleep(sleepMS);
  //delay(sleepMS);


}

void readSensors() {
  /********************************************************************/
  
    //Ambient Temperature
  getAmbientTemperature();
  
  //set DateTime
  getdateTime();

  //Temperature
  getTemperature();



  //Moisture
  getMoisture();

  //Methane
  getMethanePPM();

  //Water Level
  getWaterLevel();

  return;
}

int getTemperature(void)
{
  sensors.requestTemperatures();

  int sensorValue =  sensors.getTempFByIndex(0);

  Serial.print("Compost Temperature is: ");
  Serial.println(sensorValue);
  if (sensorValue < 0) {
    sensorValue = 0;
  }

  char charArray[5];
  dtostrf(sensorValue, 5, 0, charArray);

  compostTempF.setValue(charArray);
  return sensorValue;

}


int getMoisture(void)
{
  float sensorValue = analogRead(moistureSensorPin);
  //Serial.print(sensorValue);
  //return (sensorValue/1023)*100;

  int calcSensorValue;

  if (sensorValue < 500) {
    calcSensorValue = 30;
  }
  else if (sensorValue < 900) {
    calcSensorValue = 50;
  }
  else {
    calcSensorValue = 65;
  }

  char charArray[5];
  dtostrf(calcSensorValue, 5, 0, charArray);
  compostMoisture.setValue(charArray);

  Serial.print("Moisture is: ");
  Serial.println(calcSensorValue);

  return calcSensorValue;

}


double getMethanePPM() {

  float sensorValue = analogRead(methaneSensorPin);
  double ppm = 10.938 * exp(1.7742 * (sensorValue * 5.0 / 4095));
  //

  if (ppm < 0) {
    ppm = 0;
  }

  Serial.print("Methane PPM is: ");
  Serial.println(ppm);

  char charArray[5];
  dtostrf(ppm, 5, 0, charArray);
  methanePPM.setValue(charArray);

  return ppm;

  //float percentage = ppm/10000;
}

int getWaterLevel() {

  pinMode(waterLevelPin, INPUT_PULLUP);
  //waterLevel.setValue(digitalRead(waterLevelPin));

  int waterLevelValue = digitalRead(waterLevelPin);
  if (waterLevelValue < 0) {
    waterLevelValue = 0;
  }
  Serial.print("Water Level is: ");
  Serial.println(waterLevelValue);

  char charArray[4];
  dtostrf(waterLevelValue, 4, 0, charArray);
  waterLevel.setValue(charArray);

  return waterLevel;

}

int getAmbientTemperature() {

    Serial.print("Humidity:    "); Serial.print(sensorAmbTemp.readHumidity(), 2);
  Serial.print("\tTemperature: "); Serial.println(sensorAmbTemp.readTemperature(), 2);
  int temperatureC = sensorAmbTemp.readTemperature();

  int temperatureF = (temperatureC * 9.0 / 5.0) + 32.0;

  Serial.print("\tTemperature F: "); Serial.println(temperatureF);
  
  char charArray[5];
  dtostrf(temperatureF, 5, 0, charArray);
  ambientTempF.setValue(charArray);
  
  return temperatureF;

}

int startWaterPump() {

  //digitalWrite(pumpPin, HIGH);     //Switch Solenoid ON
  //delay(2000);                      //Wait 10 Seconds
  //digitalWrite(pumpPin, LOW);      //Switch Solenoid OFF
  //return 1;

}

void print2digits(int number) {
  if (number >= 0 && number < 10) {
    Serial.write('0');
  }
  Serial.print(number);
}

void getdateTime() {
  int datetime = now();
  char charArray[20];
  dtostrf(datetime, 20, 0, charArray);

  readingDateTime.setValue(charArray);

  Serial.print("Ok, Time = ");
  print2digits(hour());
  Serial.write(':');
  print2digits(minute());
  Serial.write(':');
  print2digits(second());
  Serial.print(", Date (D/M/Y) = ");
  Serial.print(day());
  Serial.write('/');
  Serial.print(month());
  Serial.write('/');
  Serial.print(year());
  Serial.println();
}

void printData(const unsigned char data[], int length) {
  for (int i = 0; i < length; i++) {
    unsigned char b = data[i];

    if (b < 16) {
      Serial.print("0");
    }
    //Serial.print(b);
    Serial.print(b, HEX);
    //Serial.print(b, DEC);
  }
}


