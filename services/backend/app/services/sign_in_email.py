import html

from app.services.email_branding import APP_BRAND_NAME


def build_sign_in_email(magic_link: str, magic_code: str, ttl_minutes: int) -> tuple[str, str, str]:
    subject = f"Sign in to {APP_BRAND_NAME}"
    text_body = (
        f"Your one-time sign-in code is: {magic_code}\n\n"
        "If you are signing in from an iPhone or iPad Home Screen app, return to the app and enter "
        "this code. Opening the link signs in your browser instead.\n\n"
        "Or use this one-time link to sign in:\n\n"
        f"{magic_link}\n\n"
        f"The code and link expire in {ttl_minutes} minutes."
    )
    html_body = f"""<!doctype html>
<html>
  <body style="margin:0;padding:24px;background:#f3f6fc;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#121a2f;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:#ffffff;border:1px solid #dbe3f1;border-radius:16px;padding:24px;">
            <tr>
              <td style="font-size:13px;font-weight:700;color:#4d5ddb;letter-spacing:0.4px;text-transform:uppercase;">
                {APP_BRAND_NAME}
              </td>
            </tr>
            <tr>
              <td style="padding-top:10px;font-size:22px;font-weight:750;color:#0f1f42;">
                Sign in securely
              </td>
            </tr>
            <tr>
              <td style="padding-top:8px;font-size:15px;color:#44506b;line-height:1.5;">
                Enter this one-time code in the sign-in screen:
              </td>
            </tr>
            <tr>
              <td style="padding-top:14px;font-size:30px;font-weight:800;letter-spacing:8px;color:#0f1f42;">
                {html.escape(magic_code)}
              </td>
            </tr>
            <tr>
              <td style="padding-top:12px;font-size:13px;color:#667694;line-height:1.55;">
                Using the iPhone or iPad Home Screen app? Return to the app and enter this code.
                Opening the link below signs in your browser instead.
              </td>
            </tr>
            <tr>
              <td style="padding-top:18px;">
                <a href="{html.escape(magic_link)}" style="display:inline-block;background:#173d9f;color:#ffffff;text-decoration:none;font-weight:700;font-size:15px;padding:12px 18px;border-radius:10px;">
                  Open sign-in link
                </a>
              </td>
            </tr>
            <tr>
              <td style="padding-top:14px;font-size:13px;color:#667694;line-height:1.55;">
                This code and link expire in {ttl_minutes} minutes.<br/>
                If the button does not work, copy and paste this URL:
              </td>
            </tr>
            <tr>
              <td style="padding-top:8px;">
                <div style="word-break:break-all;background:#f7f9ff;border:1px solid #dbe3f1;border-radius:10px;padding:10px 12px;font-size:12px;color:#2c3c61;">
                  {html.escape(magic_link)}
                </div>
              </td>
            </tr>
            <tr>
              <td style="padding-top:18px;font-size:12px;color:#8a96b0;line-height:1.45;">
                If you didn't request this, you can ignore this email.
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""
    return subject, text_body, html_body
