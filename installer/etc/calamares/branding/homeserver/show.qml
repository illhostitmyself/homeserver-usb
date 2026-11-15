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

    Slide {
        Text {
            anchors.centerIn: parent
            width: parent.width * 0.8
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
            font.pixelSize: 30
            color: "#2f5d62"
            text: "Your home server is being installed.<br/><br/>This takes about 10 to 20 minutes. You don't need to do anything."
        }
    }

    Slide {
        Text {
            anchors.centerIn: parent
            width: parent.width * 0.8
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
            font.pixelSize: 30
            color: "#2f5d62"
            text: "<b>When it's finished, the computer turns itself off.</b><br/><br/>Then pull out the USB stick and press the power button."
        }
    }

    Slide {
        Text {
            anchors.centerIn: parent
            width: parent.width * 0.8
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
            font.pixelSize: 30
            color: "#2f5d62"
            text: "The first start takes a few extra minutes while your apps are set up.<br/><br/>After that, open <b>http://homeserver.local</b> on any computer, phone or tablet at home."
        }
    }
}
