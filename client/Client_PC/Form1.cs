using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Drawing;
using System.Linq;
using System.Text;
using System.Windows.Forms;
using System.Net;
using System.Net.Sockets;
using System.IO;
using System.Threading;

namespace Client_PC
{
    public partial class Form1 : Form
    {
        TcpClient tcpclnt = new TcpClient();
        private int hostPort = -1;
        Thread wait = null;
        public delegate void setOutput();
        private String rcvMsg = null;
        Boolean hasNewData = false;
        public string s;
        private string currentNotice;
      
        public Form1()
        {
            InitializeComponent();
            cmd_send.Enabled = false;
            textBox3.Enabled = false;
        
        }

        public void setOut()
        {
            if (hasNewData && rcvMsg != null)
            {
                output.Text += "\n Recieved data : " + rcvMsg;
                rcvMsg = null;
                hasNewData = false;
            }
 
        }

        private void cmd_con_Click(object sender, EventArgs e)
        {
        try
            {
                output.Text += "Connecting . . ." + Environment.NewLine;
                hostPort = int.Parse(textBox2.Text);
                tcpclnt.Connect(textBox1.Text.ToString() , hostPort);
                output.Text += "Connected" + Environment.NewLine;
                cmd_send.Enabled = true;
                cmd_con.Enabled = false;
                textBox1.Enabled = false;
                textBox2.Enabled = false;
                textBox3.Enabled = true;
                wait = new Thread(new ThreadStart(waitForData));
                wait.Start();

            }
           catch (Exception ex)
            {
               output.Text += "Error..... \n Server has not started yet\n" + ex.StackTrace; 
            }
         }
        private void waitForData()
        {
            try
            {
                NetworkStream read = tcpclnt.GetStream();
                while (read.CanRead)
                {
                    byte[] buffer = new byte[64];

                    read.Read(buffer, 0, buffer.Length);
                    s = new ASCIIEncoding().GetString(buffer);
                    System.Console.WriteLine("Recieved data:" + new ASCIIEncoding().GetString(buffer));
                    rcvMsg = new ASCIIEncoding().GetString(buffer) + "\n";
                    hasNewData = true;

                    
                    bool f = false;
                    f = rcvMsg.Contains("##");
                    bool comand = false;
                    comand = rcvMsg.Contains("*+*-");
                    
                       /*File receive*/

                     if (f)
                    {
                        string d = "##";
                        rcvMsg = rcvMsg.TrimStart(d.ToCharArray());
                        int lastLt = rcvMsg.LastIndexOf("|");
                        rcvMsg = rcvMsg.Substring(0, lastLt);
                        NetworkStream ns = tcpclnt.GetStream();
                        if (ns.CanWrite)
                        {
                            string dataS = "^^Y";
                            byte[] bf = new ASCIIEncoding().GetBytes(dataS);
                            ns.Write(bf, 0, bf.Length);
                            ns.Flush();
                        }
                        try
                        {
                            new Recieve_File().recieve_file(rcvMsg);
                        }
                        catch (Exception ec)
                        {
                            System.Console.WriteLine(ec.Message);
                        }

                    }
                         /*Command-shutdown/restart/logoff*/
                    else if (comand)
                    {
                        string com = "*+*-";
                        rcvMsg = rcvMsg.TrimStart(com.ToCharArray());
                        execute_command(rcvMsg);
                    
                    }
                    else
                    {
                        this.Invoke(new setOutput(setOut));
                        Thread.Sleep(1000);
                    }


                }
            }
            catch (Exception ex)
            {
                wait.Abort();
                output.Text += "Error..... " + ex.StackTrace; 
            }
          
        }

        public delegate void addNotification();
        private void addNotice()
        {
            if (currentNotice != null)
            {
                output.Text += currentNotice;
                output.Text += Environment.NewLine;
                currentNotice = null;
            }
        }
        private void execute_command(String Comande)
        {
            if (Comande.CompareTo("shutdown") == 1)
            {
                System.Diagnostics.Process.Start("shutdown", "-s");
                currentNotice = "Shutdown initiating . . .";
                this.Invoke(new addNotification(addNotice));
                NetworkStream ns = tcpclnt.GetStream();
                String notify = "++--Shutdown Completed . . .";
                if (ns.CanWrite)
                {
                    byte[] bf = new ASCIIEncoding().GetBytes(notify);
                    ns.Write(bf, 0, bf.Length);
                    ns.Flush();
                }
               
            }

            else if (Comande.CompareTo("restart") == 1)
            {
                System.Diagnostics.Process.Start("shutdown", "-r");
                currentNotice = "Restart initiating . . .";
                this.Invoke(new addNotification(addNotice));
                NetworkStream ns = tcpclnt.GetStream();
                String notify = "++--Restart Completed . . .";
                if (ns.CanWrite)
                {
                    byte[] bf = new ASCIIEncoding().GetBytes(notify);
                    ns.Write(bf, 0, bf.Length);
                    ns.Flush();
                }


            }
            else if (Comande.CompareTo("logoff") == 1)
            {
                System.Diagnostics.Process.Start("shutdown", "-l");
                currentNotice = "Logoff initiating . . .";
                this.Invoke(new addNotification(addNotice));
                NetworkStream ns = tcpclnt.GetStream();
                String notify = "++--Logoff Completed . . .";
                if (ns.CanWrite)
                {
                    byte[] bf = new ASCIIEncoding().GetBytes(notify);
                    ns.Write(bf, 0, bf.Length);
                    ns.Flush();
                }
            }
            else if (Comande.CompareTo("abort") == 1)
            {
                System.Diagnostics.Process.Start("shutdown", "-a");
                currentNotice = "Abort initiating . . .";
                this.Invoke(new addNotification(addNotice));

                NetworkStream ns = tcpclnt.GetStream();
                String notify = "++--Abort Completed . . .";
                if (ns.CanWrite)
                {
                    byte[] bf = new ASCIIEncoding().GetBytes(notify);
                    ns.Write(bf, 0, bf.Length);
                    ns.Flush();
                }
            }
            tcpclnt.Close();
            Thread.Sleep(7000);
            Application.Restart();
        }


        private void cmd_send_Click_1(object sender, EventArgs e)
        {
   
            try
            {
                String str = textBox3.Text.ToString();
                output.Text += "\n Sent data : " + str;

            }
            catch (Exception ex)
            {
                wait.Abort();
                output.Text += "Error..... " + ex.StackTrace;

            }

            NetworkStream ns = tcpclnt.GetStream();
            String data = "";
            data = "--++" + textBox3.Text;
            if (ns.CanWrite)
            {
                byte[] bf = new ASCIIEncoding().GetBytes(data);
                ns.Write(bf, 0, bf.Length);
                ns.Flush();
            }
            textBox3.Clear();
        }

        private void cmd_dis_Click(object sender, EventArgs e)
        {
            if (wait != null)
            {
                wait.Abort();
                //read.Close(2000);
            }

            IPAddress ipclient = Dns.GetHostByName(Dns.GetHostName()).AddressList[0];
            String ipclnt = "+@@+" + ipclient.ToString();
            NetworkStream ns = tcpclnt.GetStream();
            if (ns.CanWrite)
            {
                byte[] bf = new ASCIIEncoding().GetBytes(ipclnt);
                ns.Write(bf, 0, bf.Length);
                ns.Flush();
            }

            tcpclnt.Close();
           // read.Close();
            Application.Exit();
        }

 




    }

    #region file_transer

    class Recieve_File
    {
        NetworkStream nStream;
        StreamReader readImageData;

        StringBuilder BlockData = new StringBuilder();
        bool Done = false;

        public void recieve_file(string path)
        {

            string host = Dns.GetHostName();
            Console.WriteLine("Host Name = " + host);
            IPHostEntry localip = Dns.GetHostByName(host);

            Console.WriteLine("IPAddress = " + localip.AddressList[0].ToString());

            IPAddress ipAddress = localip.AddressList[0];
            TcpListener tcpListener = new TcpListener(ipAddress, 7890);
            tcpListener.Start();

            Console.WriteLine("Waiting for resposne . . .");
            

            TcpClient tcpClient = null;

            while (tcpClient == null)
            {
                tcpClient = tcpListener.AcceptTcpClient();
            }

            Console.WriteLine("Connection Made");
            nStream = tcpClient.GetStream();
            readImageData = new StreamReader(nStream);

            string data;

            while (Done == false)
            {
                while ((data = readImageData.ReadLine()) != null)
                {
                    BlockData.Append(data);
                }

                Done = true;
            }
            byte[] byte_image = Convert.FromBase64String(BlockData.ToString());
            Console.WriteLine("->"+path + "<--");
            //path = "new.png";
            // Change File Name Here 
            if (File.Exists(path))
            {
                File.Delete(path);
            }
            FileStream fs = new FileStream(path, FileMode.Create);
            fs.Write(byte_image, 0, byte_image.Length);
            fs.Flush();
            fs.Close();
            fs.Dispose();
            fs = null;
            Console.WriteLine("File has been recieved!");
            MessageBox.Show("Connection Made\n" + path + "\nFile has been recieved!");
            //System.Diagnostics.Process.Start("run.exe");

            readImageData.Close();
            tcpClient.Close();
            nStream.Dispose();
            tcpListener.Stop();
        }
    }

    #endregion

}
