// Slideshow for "Update this server" (branding homeserver-update, made by update-setup.sh).
import QtQuick 2.0;
import calamares.slideshow 1.0;

Presentation
{
    id: presentation

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
        message: "Your server is being updated.<br/><br/>This takes a few minutes. Nothing is erased, and you don't need to do anything."
    }
}
