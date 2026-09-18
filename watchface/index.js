var W = 390
var H = 450
var TIME_X = 36
var TIME_Y = 26
var DW = 69
var DH = 68
var CW = 21
var CH = 54
var DIGIT_SPACE = 10
var DATE_Y = 100
var DATE_DW = 30
var DATE_SLASH = 15
var FOOTER_Y = 400
var DATA_DW = 21
var LABEL_HR_W = 39
var HR_X = 32
var BAT_BAR_X = 284
var MARS_FRAMES = 48
var built = false

function pad2(n) {
  return n < 10 ? '0' + n : '' + n
}

function timeDigits() {
  return [
    'time/0.png',
    'time/1.png',
    'time/2.png',
    'time/3.png',
    'time/4.png',
    'time/5.png',
    'time/6.png',
    'time/7.png',
    'time/8.png',
    'time/9.png',
  ]
}

function dataDigits() {
  return [
    'data/0.png',
    'data/1.png',
    'data/2.png',
    'data/3.png',
    'data/4.png',
    'data/5.png',
    'data/6.png',
    'data/7.png',
    'data/8.png',
    'data/9.png',
  ]
}

function dateDigits() {
  return [
    'date/0.png',
    'date/1.png',
    'date/2.png',
    'date/3.png',
    'date/4.png',
    'date/5.png',
    'date/6.png',
    'date/7.png',
    'date/8.png',
    'date/9.png',
  ]
}

function batteryFrames() {
  return [
    'battery/0.png',
    'battery/1.png',
    'battery/2.png',
    'battery/3.png',
    'battery/4.png',
    'battery/5.png',
    'battery/6.png',
    'battery/7.png',
    'battery/8.png',
    'battery/9.png',
    'battery/10.png',
  ]
}

function currentHour(timeSensor) {
  var hour = 0
  if (timeSensor && typeof timeSensor.hour === 'number') {
    hour = timeSensor.hour
  }
  if (hour < 0 || hour > 23) {
    hour = 0
  }
  return hour
}

function marsSlot(timeSensor) {
  var hour = currentHour(timeSensor)
  var minute = 0
  if (timeSensor && typeof timeSensor.minute === 'number') {
    minute = timeSensor.minute
  }
  if (minute < 0) {
    minute = 0
  }
  if (minute > 59) {
    minute = 59
  }
  return Math.floor((hour * 60 + minute) / 30) % MARS_FRAMES
}

function marsPath(slot) {
  return 'mars/' + pad2(slot) + '.png'
}

function make() {
  if (built) {
    return
  }
  built = true

  var digits = timeDigits()
  var small = dataDigits()
  var dateImgs = dateDigits()
  var timeSensor = hmSensor.createSensor(hmSensor.id.TIME)
  var slot = marsSlot(timeSensor)

  var marsImg = hmUI.createWidget(hmUI.widget.IMG, {
    x: 0,
    y: 0,
    w: W,
    h: H,
    src: marsPath(slot),
  })

  hmUI.createWidget(hmUI.widget.IMG_TIME, {
    hour_zero: 1,
    hour_startX: TIME_X,
    hour_startY: TIME_Y,
    hour_array: digits,
    hour_space: DIGIT_SPACE,
  })

  hmUI.createWidget(hmUI.widget.IMG, {
    x: TIME_X + DW * 2 + DIGIT_SPACE,
    y: TIME_Y + Math.floor((DH - CH) / 2),
    w: CW,
    h: CH,
    src: 'time/colon.png',
  })

  hmUI.createWidget(hmUI.widget.IMG_TIME, {
    minute_zero: 1,
    minute_startX: TIME_X + DW * 2 + DIGIT_SPACE + CW,
    minute_startY: TIME_Y,
    minute_array: digits,
    minute_space: DIGIT_SPACE,
  })

  // Center a typical M/D like 9/18 (1 digit month, slash, 2 digit day).
  var dateX = Math.floor((W - (DATE_DW + DATE_SLASH + DATE_DW * 2)) / 2)
  hmUI.createWidget(hmUI.widget.IMG_DATE, {
    month_startX: dateX,
    month_startY: DATE_Y,
    month_en_array: dateImgs,
    month_sc_array: dateImgs,
    month_tc_array: dateImgs,
    month_zero: 0,
    month_space: 0,
    month_unit_en: 'date/slash.png',
    month_unit_sc: 'date/slash.png',
    month_unit_tc: 'date/slash.png',
    day_follow: 1,
    day_zero: 0,
    day_en_array: dateImgs,
    day_sc_array: dateImgs,
    day_tc_array: dateImgs,
    day_space: 0,
  })

  hmUI.createWidget(hmUI.widget.IMG, {
    x: HR_X,
    y: FOOTER_Y,
    src: 'data/label_hr.png',
  })
  hmUI.createWidget(hmUI.widget.TEXT_IMG, {
    x: HR_X + LABEL_HR_W + 6,
    y: FOOTER_Y,
    w: DATA_DW * 3 + 4,
    h: 22,
    type: hmUI.data_type.HEART,
    font_array: small,
    h_space: 1,
    invalid_image: 'data/dash.png',
  })

  var batFrames = batteryFrames()
  var batBar = hmUI.createWidget(hmUI.widget.IMG_LEVEL, {
    x: BAT_BAR_X,
    y: FOOTER_Y,
    w: 76,
    h: 22,
    image_array: batFrames,
    image_length: 11,
  })

  var batterySensor = hmSensor.createSensor(hmSensor.id.BATTERY)
  function updateBatBar() {
    var pct = 0
    if (batterySensor && typeof batterySensor.current === 'number') {
      pct = batterySensor.current
    }
    if (pct < 0) {
      pct = 0
    }
    if (pct > 100) {
      pct = 100
    }
    var lvl = Math.floor((pct + 5) / 10)
    if (lvl > 10) {
      lvl = 10
    }
    batBar.setProperty(hmUI.prop.LEVEL, lvl)
  }
  updateBatBar()

  var lastSlot = slot
  if (typeof timer !== 'undefined' && timer.createTimer) {
    timer.createTimer(60000, 60000, function () {
      var next = marsSlot(timeSensor)
      if (next !== lastSlot) {
        lastSlot = next
        marsImg.setProperty(hmUI.prop.SRC, marsPath(next))
      }
      updateBatBar()
    })
  }
}

WatchFace({
  onInit: function () {},
  build: function () {
    make()
  },
  init_view: function () {
    make()
  },
  onReady: function () {
    make()
  },
  onDestroy: function () {},
})
