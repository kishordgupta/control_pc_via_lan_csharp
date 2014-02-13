namespace Client_PC
{
    partial class Form1
    {
        /// <summary>
        /// Required designer variable.
        /// </summary>
        private System.ComponentModel.IContainer components = null;

        /// <summary>
        /// Clean up any resources being used.
        /// </summary>
        /// <param name="disposing">true if managed resources should be disposed; otherwise, false.</param>
        protected override void Dispose(bool disposing)
        {
            if (disposing && (components != null))
            {
                components.Dispose();
            }
            base.Dispose(disposing);
        }

        #region Windows Form Designer generated code

        /// <summary>
        /// Required method for Designer support - do not modify
        /// the contents of this method with the code editor.
        /// </summary>
        private void InitializeComponent()
        {
            this.output = new System.Windows.Forms.RichTextBox();
            this.label1 = new System.Windows.Forms.Label();
            this.textBox1 = new System.Windows.Forms.TextBox();
            this.label2 = new System.Windows.Forms.Label();
            this.textBox2 = new System.Windows.Forms.TextBox();
            this.cmd_con = new System.Windows.Forms.Button();
            this.cmd_send = new System.Windows.Forms.Button();
            this.textBox3 = new System.Windows.Forms.TextBox();
            this.label3 = new System.Windows.Forms.Label();
            this.cmd_dis = new System.Windows.Forms.Button();
            this.SuspendLayout();
            // 
            // output
            // 
            this.output.BackColor = System.Drawing.SystemColors.Window;
            this.output.ForeColor = System.Drawing.SystemColors.WindowText;
            this.output.Location = new System.Drawing.Point(0, -1);
            this.output.Name = "output";
            this.output.ReadOnly = true;
            this.output.Size = new System.Drawing.Size(367, 128);
            this.output.TabIndex = 0;
            this.output.Text = "";
            // 
            // label1
            // 
            this.label1.AutoSize = true;
            this.label1.Location = new System.Drawing.Point(21, 145);
            this.label1.Name = "label1";
            this.label1.Size = new System.Drawing.Size(51, 13);
            this.label1.TabIndex = 1;
            this.label1.Text = "Server IP";
            // 
            // textBox1
            // 
            this.textBox1.Location = new System.Drawing.Point(88, 142);
            this.textBox1.Name = "textBox1";
            this.textBox1.Size = new System.Drawing.Size(130, 20);
            this.textBox1.TabIndex = 2;
            // 
            // label2
            // 
            this.label2.AutoSize = true;
            this.label2.Location = new System.Drawing.Point(21, 176);
            this.label2.Name = "label2";
            this.label2.Size = new System.Drawing.Size(60, 13);
            this.label2.TabIndex = 3;
            this.label2.Text = "Server Port";
            // 
            // textBox2
            // 
            this.textBox2.Location = new System.Drawing.Point(88, 173);
            this.textBox2.Name = "textBox2";
            this.textBox2.Size = new System.Drawing.Size(100, 20);
            this.textBox2.TabIndex = 4;
            this.textBox2.Text = "800";
            // 
            // cmd_con
            // 
            this.cmd_con.Location = new System.Drawing.Point(271, 266);
            this.cmd_con.Name = "cmd_con";
            this.cmd_con.Size = new System.Drawing.Size(75, 23);
            this.cmd_con.TabIndex = 5;
            this.cmd_con.Text = "Connect";
            this.cmd_con.UseVisualStyleBackColor = true;
            this.cmd_con.Click += new System.EventHandler(this.cmd_con_Click);
            // 
            // cmd_send
            // 
            this.cmd_send.Location = new System.Drawing.Point(181, 266);
            this.cmd_send.Name = "cmd_send";
            this.cmd_send.Size = new System.Drawing.Size(75, 23);
            this.cmd_send.TabIndex = 6;
            this.cmd_send.Text = "Send";
            this.cmd_send.UseVisualStyleBackColor = true;
            this.cmd_send.Click += new System.EventHandler(this.cmd_send_Click_1);
            // 
            // textBox3
            // 
            this.textBox3.Location = new System.Drawing.Point(88, 208);
            this.textBox3.Name = "textBox3";
            this.textBox3.Size = new System.Drawing.Size(204, 20);
            this.textBox3.TabIndex = 7;
            // 
            // label3
            // 
            this.label3.AutoSize = true;
            this.label3.Location = new System.Drawing.Point(21, 208);
            this.label3.Name = "label3";
            this.label3.Size = new System.Drawing.Size(50, 13);
            this.label3.TabIndex = 8;
            this.label3.Text = "Message";
            // 
            // cmd_dis
            // 
            this.cmd_dis.Location = new System.Drawing.Point(88, 266);
            this.cmd_dis.Name = "cmd_dis";
            this.cmd_dis.Size = new System.Drawing.Size(77, 23);
            this.cmd_dis.TabIndex = 9;
            this.cmd_dis.Text = "Disconnect";
            this.cmd_dis.UseVisualStyleBackColor = true;
            this.cmd_dis.Click += new System.EventHandler(this.cmd_dis_Click);
            // 
            // Form1
            // 
            this.AutoScaleDimensions = new System.Drawing.SizeF(6F, 13F);
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.ClientSize = new System.Drawing.Size(367, 313);
            this.Controls.Add(this.cmd_dis);
            this.Controls.Add(this.label3);
            this.Controls.Add(this.textBox3);
            this.Controls.Add(this.cmd_send);
            this.Controls.Add(this.cmd_con);
            this.Controls.Add(this.textBox2);
            this.Controls.Add(this.label2);
            this.Controls.Add(this.textBox1);
            this.Controls.Add(this.label1);
            this.Controls.Add(this.output);
            this.Name = "Form1";
            this.Text = "Client_PC";
            this.ResumeLayout(false);
            this.PerformLayout();

        }

        #endregion

        private System.Windows.Forms.RichTextBox output;
        private System.Windows.Forms.Label label1;
        private System.Windows.Forms.TextBox textBox1;
        private System.Windows.Forms.Label label2;
        private System.Windows.Forms.TextBox textBox2;
        private System.Windows.Forms.Button cmd_con;
        private System.Windows.Forms.Button cmd_send;
        private System.Windows.Forms.TextBox textBox3;
        private System.Windows.Forms.Label label3;
        private System.Windows.Forms.Button cmd_dis;
    }
}

