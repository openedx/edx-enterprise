var lastTrackedEvent = "";
var lastTrackedForm = {};
var analytics = {
    track: function (eventName) {
        lastTrackedEvent = eventName;
    },
    trackForm: function (form, callback) {
        lastTrackedForm = {
            form: form,
            callback: callback
        };
    }
};
