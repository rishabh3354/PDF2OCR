ERROR_MESSAGE = """
*****Unable to fetch data from file******

Please provide Good Quality Images/PDF files.

Reason for Failure:

1. File is not of Good quality.
2. Image DPI is very less.
3. File/image format is not supported.
4. OCR is not able to read your file.

"""

BUYMECOFEE = """

<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
body{
    background:#edf2f7;
    margin:10px;
    font-family:"Segoe UI",Arial,sans-serif;
    color:#2d3748;
}

.card{
    width:440px;
    background:#ffffff;
    border:1px solid #dfe5ec;
    border-radius:12px;
}

.title{
    font-size:24px;
    font-weight:bold;
    color:#222;
    text-align:center;
}

.quote{
    background:#f7fafc;
    border-left:4px solid #31bb42;
    padding:12px;
    color:#555;
    font-style:italic;
    line-height:22px;
    border-radius:6px;
    text-align:center;
}

.message{
    font-size:14px;
    line-height:22px;
    text-align:center;
}

.green{
    color:#31bb42;
    font-weight:bold;
}

.warning{
    background:#FFF8E1;
    border:1px solid #FFD54F;
    color:#7A5B00;
    border-radius:8px;
    text-align:center;
}

.warning-title{
    font-size:16px;
    font-weight:bold;
    margin-bottom:8px;
}

a.button{
    display:inline-block;
    background:#31bb42;
    color:#ffffff;
    text-decoration:none;
    font-weight:bold;
    font-size:16px;
    padding:12px 30px;
    border-radius:24px;
}
</style>
</head>

<body>

<table align="center" class="card" cellspacing="0" cellpadding="0">

    <tr>
        <td align="center" style="padding-top:12px;">

            <img src=":/myresource/resource/sales_and_support.png"
                 width="360"
                 style="display:block;">

        </td>
    </tr>

    <tr>
        <td style="padding:18px;" align="center">

            <div class="title">
                Support Development
            </div>

            <br>

            <div class="quote">

                "The happiest people are not those getting more,<br>
                but those giving more."

                <br><br>

                <b>— H. Jackson Brown Jr.</b>

            </div>

            <br>

            <div class="message">

                Every contribution helps improve this application,
                add new features, fix bugs and keep future updates free.

                <br><br>

                <span class="green">
                    Thank you for supporting independent software.
                </span>

            </div>

            <br>

            <a class="button"
               href="https://www.paypal.com/paypalme/rishabh3354/5">

                Support via PayPal

            </a>

            <br><br>

            <table class="warning"
                   width="100%"
                   cellpadding="12"
                   cellspacing="0">

                <tr>

                    <td align="center">

                        <h3>** OCR Accuracy Warning **</h3>

                        OCR results are generated using <b>Tesseract</b> and may not
                        be 100% accurate.

                        Recognition quality depends on the image resolution,
                        text clarity, language, font and document quality.

                        <br><br>

                        <b>
                            Please review and verify the extracted text before
                            using it for important or official purposes.
                        </b>

                    </td>

                </tr>

            </table>

        </td>
    </tr>

</table>

</body>
</html>

"""
