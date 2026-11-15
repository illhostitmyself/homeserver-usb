import QtQuick 2.0;
import calamares.slideshow 1.0;

Presentation
{
    id: presentation

    Timer {
        interval: 15000
        repeat: true
        running: true
        onTriggered: presentation.goToNextSlide()
    }

    component Step: Slide {
        property string message
        Image {
            id: art
            source: "slide.png"
            width: Math.min(parent.width * 0.45, 420)
            fillMode: Image.PreserveAspectFit
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: parent.top
            anchors.topMargin: parent.height * 0.08
        }
        Text {
            anchors.top: art.bottom
            anchors.topMargin: 30
            anchors.horizontalCenter: parent.horizontalCenter
            width: parent.width * 0.8
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
            font.pixelSize: 28
            color: "#253457"
            textFormat: Text.RichText
            text: message
        }
    }

    Step {
        message: "Your home server is being installed.<br/><br/>This takes 15 to 30 minutes, most of it downloading your apps. You don't need to do anything."
    }
    Step {
        message: "<b><font color='#FB4D13'>When it's finished, the computer turns itself off.</font></b><br/><br/>Then pull out the USB stick and press the power button."
    }
    Step {
        message: "After that, your dashboard opens on this screen.<br/><br/>From any computer, phone or tablet at home, open <b>http://homeserver.local</b>"
    }
}
