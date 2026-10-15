from logging import getLogger
from django.db import migrations

LOGGER = getLogger(__name__)

def update_email(apps, schema_editor):
    email_template = apps.get_model('enterprise', 'EnrollmentNotificationEmailTemplate')
    email_template.objects.update_or_create(
            template_type='ADMIN_ENROLL',
            defaults={'html_template': """
<html>
<head>
    <style type="text/css">
        a, a:visited, a:hover, a:active {
            text-decoration: none;
            color: #00262b;
        }
    </style>
</head>
<body>
    <table style="max-width: 650;" align="center">
        <tbody>
            <tr>
            <td>
                <table width="100%" cellspacing="0" cellpadding="0" role="presentation" style="border-collapse:collapse;border-spacing:0px">
                    <tbody>
                        <tr>
                        <td align="left" valign="top" style="padding:8px;Margin:0;width:560px">
                            <img src="https://ci3.googleusercontent.com/proxy/ZAml-YgIIJEht-OBl6GqLNIUeVKLyPvs_ldFo9FShp-andj1YQxvliJXv_s_Tmh6cg1-5avJJmvXmzxbQp06sB_WUeYYkN9kzV6jtVUvYKPPjUX_8_iFJAZqsNqYakl4nQyHnl0dClFzxiaLuULSPoqGPLBfJmNOEXIBYkvKYa95640xvHwDiQ22bZ16=s0-d-e1-ft#https://appboy-images.com/appboy/communication/assets/image_assets/images/5fc568622213594dcbda2623/original.png?1606772834" width="110" height="57" border="0" style="display:block" alt="edX" id="m_-37988256656304111logo" class="CToWUd">
                        </td>
                        <td align="right" valign="top" style="white-space:nowrap;text-decoration:none;color:#00262b;font-family:'inter',Arial,sans-serif;font-size:18px;line-height:21px">
                            <a href="{{dashboard_url}}">My Dashboard</a> 
                        </td>
                        </tr>
                    </tbody>
                </table>
            </td>
            </tr>
            <tr>
            <td align="left" bgcolor="#002b2b" style="Margin:0;padding-left:20px;padding-right:20px;padding-top:40px;padding-bottom:40px;background-color:#002b2b;background-image:url(https://ci3.googleusercontent.com/proxy/2CLnc9QL2u1L0MsUErVcQVBOz6OlDew2A5O8umOI9v7PGI3ip8YnJqYPRcexkjGsbNvNa6kUFyuHAMp7LlVBKKa7bxaKUjEO566AyX4M_6PhDtwz-QpLXLg9eQZQ93LIwP-5SbUtfxd203xXFTVBatJrN9P2hsuJSWFwd9k2pooiea6Qsg=s0-d-e1-ft#https://fzvpwi.stripocdn.email/content/guids/CABINET_4d3c6887b8ac137f656a3dd54bb5f6c8/images/53481614126118338.png);background-repeat:no-repeat;background-position:left top" background="https://ci3.googleusercontent.com/proxy/2CLnc9QL2u1L0MsUErVcQVBOz6OlDew2A5O8umOI9v7PGI3ip8YnJqYPRcexkjGsbNvNa6kUFyuHAMp7LlVBKKa7bxaKUjEO566AyX4M_6PhDtwz-QpLXLg9eQZQ93LIwP-5SbUtfxd203xXFTVBatJrN9P2hsuJSWFwd9k2pooiea6Qsg=s0-d-e1-ft#https://fzvpwi.stripocdn.email/content/guids/CABINET_4d3c6887b8ac137f656a3dd54bb5f6c8/images/53481614126118338.png">
                <table cellpadding="0" cellspacing="0" width="100%" style="border-collapse:collapse;border-spacing:0px">
                    <tbody>
                        <tr>
                        <td align="center" valign="top" style="padding:0;Margin:0;width:560px">
                            <table cellpadding="0" cellspacing="0" width="100%" role="presentation" style="border-collapse:collapse;border-spacing:0px">
                                <tbody>
                                    <tr>
                                    <td align="center" style="padding:0;Margin:0">
                                        <p style="Margin:0;font-size:32px;font-family:helvetica,'helvetica neue',arial,verdana,sans-serif;line-height:48px;color:#ffffff"><strong><span class="il">Congratulations</span>, Restless Learner</strong></p>
                                    </td>
                                    </tr>
                                    <tr>
                                    <td align="center" style="padding:0;Margin:0">
                                        <p style="Margin:0;font-size:20px;font-family:arial,'helvetica neue',helvetica,sans-serif;line-height:30px;color:#ffffff">Great News! You've been <span class="il">Enrolled</span> in {{enrolled_in.name}} by {{organization_name}}</p>
                                    </td>
                                    </tr>
                                </tbody>
                            </table>
                        </td>
                        </tr>
                    </tbody>
                </table>
            </td>
            </tr>
            <tr>
            <td align="left" style="padding:0;Margin:0;padding-top:20px;padding-left:20px;padding-right:20px">
                <table cellpadding="0" cellspacing="0" width="100%" style="border-collapse:collapse;border-spacing:0px">
                    <tbody>
                        <tr>
                        <td align="center" valign="top" style="padding:0;Margin:0;width:560px">
                            <table cellpadding="0" cellspacing="0" width="100%" role="presentation" style="border-collapse:collapse;border-spacing:0px">
                                <tbody>
                                    <tr>
                                    <td align="center" style="padding:0;Margin:0">
                                        <p style="Margin:0;font-size:14px;font-family:arial,'helvetica neue',helvetica,sans-serif;line-height:21px;color:#333333">
                                            This course is a free benefit offered especially for you, and we are excited for you to meet your learning community on edX.
                                        </p>
                                    </td>
                                    </tr>
                                </tbody>
                            </table>
                        </td>
                        </tr>
                    </tbody>
                </table>
            </td>
            </tr>
            <tr>
            <td>
                <table width="100%" cellspacing="0" cellpadding="0" role="presentation" style="border-collapse:collapse;border-spacing:0px">
                    <tbody>
                        <tr>
                        <td align="center" bgcolor="#ffffff" style="padding:0;Margin:0;padding-top:10px;padding-left:10px;padding-bottom:15px"><span class="m_-37988256656304111es-button-border" style="border-style:solid;border-color:#d03529;background:#d03529;border-width:0px 0px 2px 0px;display:inline-block;border-radius:0px;width:auto"><a href="{{enrolled_in.url}}" class="m_-37988256656304111es-button" style="text-decoration:none;font-family:helvetica,'helvetica neue',arial,verdana,sans-serif;font-size:18px;color:#ffffff;border-style:solid;border-color:#d03529;border-width:10px 15px;display:inline-block;background:#d03529;border-radius:0px;font-weight:normal;font-style:normal;line-height:22px;width:auto;text-align:center" target="_blank">Start my course</a></span></td>
                        </tr>
                    </tbody>
                </table>
            </td>
            </tr>
            <tr>
            <td align="center" bgcolor="#ffffff" style="padding:20px;Margin:0;background-color:#ffffff">
                <table cellpadding="0" cellspacing="0" class="m_-37988256656304111es-left" align="center" style="display:inline-block;border-collapse:collapse;border-spacing:0px;">
                    <tbody>
                        <tr>
                        <td class="m_-37988256656304111es-m-p0r" align="center" style="padding:0;Margin:0;width:50px">
                            <table cellpadding="0" cellspacing="0" width="100%" role="presentation" style="border-collapse:collapse;border-spacing:0px">
                                <tbody>
                                    <tr>
                                    <td align="center" style="padding:0;Margin:0;font-size:0px"><a href="https://www.facebook.com/edX"><img src="https://ci3.googleusercontent.com/proxy/2EBI4EepyVUk0cIRxzfMGmsBqU6TKjJsw7CqB8hSM0zRlLb0-BL0Y_JXhu-E6b1DiMGQ-4NHHem0qkjDgG_0xHNTYSsmJ0Rv9qBXCj2SJyT-yFlrkA7SYr4YkGg8CdkRYlkwZsQzU0DiZIDWZopRyOkPvcHWVTLwzCdJMKZcFc57HfR-eQ=s0-d-e1-ft#https://fzvpwi.stripocdn.email/content/guids/CABINET_4d3c6887b8ac137f656a3dd54bb5f6c8/images/71001614127047298.png" alt="facebook logo hyperlink" style="display:block;border:0;outline:none;text-decoration:none" width="35" height="35" class="CToWUd"></a></td>
                                    </tr>
                                </tbody>
                            </table>
                        </td>
                        <td class="m_-37988256656304111es-hidden" style="padding:0;Margin:0;width:15px"></td>
                        </tr>
                    </tbody>
                </table>
                <table cellpadding="0" cellspacing="0" class="m_-37988256656304111es-left" align="center" style="display:inline-block;border-collapse:collapse;border-spacing:0px;">
                    <tbody>
                        <tr>
                        <td align="center" style="padding:0;Margin:0;width:50px">
                            <table cellpadding="0" cellspacing="0" width="100%" role="presentation" style="border-collapse:collapse;border-spacing:0px">
                                <tbody>
                                    <tr>
                                    <td align="center" style="padding:0;Margin:0;font-size:0px"><a href="https://twitter.com/edXOnline"><img src="https://ci4.googleusercontent.com/proxy/yPnmVX7UE9sXw9LbZmrtTLvkrZVy9NJurDVqU6aByY871Dj0GMzEmJZOQm5kTImdMT_qNIIvpVpTpTpboYZB6wPyZuOUKwd49j6Q7yTB9IM0DWSMdldQ4XiOHReWms7Mw7HL9rRGk1iRLwmx0IT5frUGIcmc4ulwvQcjBFSHUBcMBDrAvQ=s0-d-e1-ft#https://fzvpwi.stripocdn.email/content/guids/CABINET_4d3c6887b8ac137f656a3dd54bb5f6c8/images/19131614127052508.png" alt="twitter logo hyperlink" style="display:block;border:0;outline:none;text-decoration:none" width="35" height="35" class="CToWUd"></a></td>
                                    </tr>
                                </tbody>
                            </table>
                        </td>
                        <td class="m_-37988256656304111es-hidden" style="padding:0;Margin:0;width:15px"></td>
                        </tr>
                    </tbody>
                </table>
                <table cellpadding="0" cellspacing="0" class="m_-37988256656304111es-left" align="center" style="display:inline-block;border-collapse:collapse;border-spacing:0px">
                    <tbody>
                        <tr>
                        <td align="center" style="padding:0;Margin:0;width:50px">
                            <table cellpadding="0" cellspacing="0" width="100%" role="presentation" style="border-collapse:collapse;border-spacing:0px">
                                <tbody>
                                    <tr>
                                    <td align="center" style="padding:0;Margin:0;font-size:0px"><a href="https://www.linkedin.com/school/edx/"><img src="https://ci6.googleusercontent.com/proxy/GT773Vs37lIPuUvoTpVMvtQ8sSuiC9sGLGtWGNti6nwmrZGrcewvoO_zFG4XJadUV-xPRYqf9zbLEshuVcSQMZiI1yUuM5VKxTF9lLfuzDWV1ZbMPEpk2cAWEZcDAW8mD3VFxY5l0y1Gxvcc_2bB4L-ApvPHnnIw7rXB_XDe1o37B4xPaA=s0-d-e1-ft#https://fzvpwi.stripocdn.email/content/guids/CABINET_4d3c6887b8ac137f656a3dd54bb5f6c8/images/42721614127058646.png" alt="linkedin logo hyperlink" style="display:block;border:0;outline:none;text-decoration:none" width="35" height="35" class="CToWUd"></a></td>
                                    </tr>
                                </tbody>
                            </table>
                        </td>
                        <td class="m_-37988256656304111es-hidden" style="padding:0;Margin:0;width:15px"></td>
                        </tr>
                    </tbody>
                </table>
                <table cellpadding="0" cellspacing="0" class="m_-37988256656304111es-left" align="center" style="display:inline-block;border-collapse:collapse;border-spacing:0px">
                    <tbody>
                        <tr>
                        <td align="center" style="padding:0;Margin:0;width:50px">
                            <table cellpadding="0" cellspacing="0" width="100%" role="presentation" style="border-collapse:collapse;border-spacing:0px">
                                <tbody>
                                    <tr>
                                    <td align="center" style="padding:0;Margin:0;font-size:0px"><a href="https://www.reddit.com/r/edX/"><img src="https://ci6.googleusercontent.com/proxy/hVT_30jYZguhmOyUAcTTZhCNDjjlivo3GAljGnyt_nNnjp0A0zcheoKw-XgM2NSD7M-CemzJEui6RIte_cH0YyJXUwCJWFpZ6j96QCB3T2UeQddtN1_VrVyQoDnAR1G82cHdJnq6Ysc-KQPvBKngjYaaPYSvcvMuHR0QS7dcnlGK35dUlA=s0-d-e1-ft#https://fzvpwi.stripocdn.email/content/guids/CABINET_4d3c6887b8ac137f656a3dd54bb5f6c8/images/23371614127063365.png" alt="reddit logo hyperlink" style="display:block;border:0;outline:none;text-decoration:none" width="35" height="35" class="CToWUd"></a></td>
                                    </tr>
                                </tbody>
                            </table>
                        </td>
                        <td class="m_-37988256656304111es-hidden" style="padding:0;Margin:0;width:15px"></td>
                        </tr>
                    </tbody>
                </table>
                <table cellpadding="0" cellspacing="0" class="m_-37988256656304111es-left" align="center" style="display:inline-block;border-collapse:collapse;border-spacing:0px;">
                    <tbody>
                        <tr>
                        <td align="left" style="padding:0;Margin:0;width:50px">
                            <table cellpadding="0" cellspacing="0" width="100%" role="presentation" style="border-collapse:collapse;border-spacing:0px">
                                <tbody>
                                    <tr>
                                    <td align="center" style="padding:0;Margin:0;font-size:0px"><a href="https://api.whatsapp.com/send?text=edX"><img src="https://ci4.googleusercontent.com/proxy/9UmWL708u3GDWbf_b3dzLoavIieL1kLHnipq6vGF06ZpMlLEQe9WkHJZsNVHfBwYZhpp71tbA8EJgf2_mhGV2RwDBIiUox83T4sP6uZKF3rw6QGEtQY2Ou16eR6v39Quf2AHsnh78t6JK6PMqlxGVSVKB2WkmUX37_2jtgfIqVtOLlV1bw=s0-d-e1-ft#https://fzvpwi.stripocdn.email/content/guids/CABINET_4d3c6887b8ac137f656a3dd54bb5f6c8/images/18781614127069989.png" alt="whatsapp logo hyperlink" style="display:block;border:0;outline:none;text-decoration:none" width="35" height="35" class="CToWUd"></a></td>
                                    </tr>
                                </tbody>
                            </table>
                        </td>
                        </tr>
                    </tbody>
                </table>
            </td>
            </tr>
            <tr>
            <td>
                <table cellpadding="0" cellspacing="0" width="100%">
                    <tbody>
                        <tr>
                        <td height="20" style="line-height:1px;font-size:1px"></td>
                        </tr>
                        <tr>
                        <td align="left" valign="top"><a href="https://business.edx.org" style="font-family:'Open Sans',Arial,sans-serif;font-size:14px;line-height:17px;text-decoration:none;color:#707070" target="_blank"><span style="color:#00262b">edX for Business</span><span style="color:#707070"> — eLearning Solutions for Your Company</span></a></td>
                        </tr>
                        <tr>
                        <td height="20" style="line-height:1px;font-size:1px"></td>
                        </tr>
                        <tr>
                        <td align="left" style="font-family:'Open Sans',Arial,sans-serif;color:#707070;font-size:14px;line-height:17px" valign="top">© 2021 edX Inc. All rights reserved.</td>
                        </tr>
                        <tr>
                        <td height="20" style="line-height:1px;font-size:1px"></td>
                        </tr>
                        <tr>
                        <td height="20" style="line-height:1px;font-size:1px"></td>
                        </tr>
                        <tr>
                        <td align="left" style="font-family:'Open Sans',Arial,sans-serif;color:#707070;font-size:14px;line-height:17px" valign="top">141 Portland St. 9th Floor, Cambridge, MA 02139</td>
                        </tr>
                        <tr>
                        <td height="30" style="line-height:1px;font-size:1px"></td>
                        </tr>
                    </tbody>
                </table>
            </td>
            </tr>
        </tbody>
    </table>
</body>
</html>
         """},
    )

class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0136_auto_20210629_2129'),
    ]

    operations = [
        migrations.RunPython(code=update_email, reverse_code=update_email)

    ]
